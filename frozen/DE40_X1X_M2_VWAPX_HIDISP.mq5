//+------------------------------------------------------------------+
//| DE40_X1X_M2_VWAPX.mq5                                             |
//| Module 2 candidate (2nd attempt): VWAP-EXTENSION MEAN REVERSION   |
//| GEN-1 baseline, self-healing campaign.                            |
//|                                                                    |
//| Edge: session VWAP (07:00 GMT reset, tick-volume weighted) is a    |
//| dynamic intraday fair-value anchor. When price extends far BELOW    |
//| VWAP and a completed M15 bar CLOSES back above the extension line, |
//| the downside extension has exhausted -> fade back up (long).       |
//|                                                                    |
//| Long-only (DE40 2023-25 shorts net-negative). One entry/day.       |
//| Fixed 1R target. Full point-in-time telemetry.                     |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 X1X Module 2 VWAPX - VWAP-extension mean reversion (long), forensic telemetry"

#include <Trade\Trade.mqh>
CTrade trade;

//---- inputs ------------------------------------------------------------
input group "=== Symbol / Timing ==="
input string InpSymbolOverride = "";          // override symbol (empty=auto-detect)
input int    InpServerUTC      = 3;           // server UTC offset hours (PU Prime=3)

input group "=== Session VWAP ==="
input int    InpVwapStartGMT = 7;             // session VWAP anchor GMT hour (inclusive)

input group "=== Entry ==="
input double InpVwapExtATR   = 1.5;           // extension threshold below VWAP (ATR15)
input int    InpEntryStartGMT = 7;            // entries from GMT hour (inclusive)
input int    InpEntryEndGMT   = 17;           // entries until GMT hour (exclusive)
input double InpSLBufATR     = 0.30;          // stop buffer below extension extreme
input double InpTP_RR        = 1.0;           // fixed target in R
input bool   InpAllowLong    = true;
input bool   InpAllowShort   = false;

input group "=== GEN-2 Evidence Gates ==="
input bool   InpGateDisp = false;            // require f_disp >= InpDispMin (impulsive extensions)
input double InpDispMin  = 0.80;             // min displacement (max 3-bar body / ATR15)

input group "=== Risk / Safety ==="
input double InpLots         = 0.10;
input int    InpMaxSpreadPts = 400;
input int    InpMagic        = 4700;
input int    InpColdStartSec = 30;

//---- globals -----------------------------------------------------------
string   g_activeSymbol = "";
datetime g_attachTime = 0;
datetime g_lastM15 = 0;
datetime g_lastD1  = 0;

// extension state
bool     g_extActive = false;
bool     g_entryDoneForDay = false;
double   g_extExtreme = 0;
double   g_vwap = 0;

// position state
bool     g_inPosition = false;
int      g_posDir = 0;
double   g_entryPrice = 0, g_sl = 0, g_tp = 0;
double   g_riskPts = 0;
double   g_mfeR = 0, g_maeR = 0;
datetime g_entryTime = 0;
int      g_entryDow = 0, g_entryHour = 0;
string   g_entrySession = "";

// indicator handles
int      g_hATR15   = INVALID_HANDLE;
int      g_hEMA200  = INVALID_HANDLE;
int      g_hEMA20H1 = INVALID_HANDLE;
int      g_hEMA50H1 = INVALID_HANDLE;

// point-in-time telemetry (f_*)
double   g_f_vwap_dist_atr = 0;
double   g_f_vwap_ext_atr  = 0;
double   g_f_reclaim_atr   = 0;
double   g_f_price_ema200  = 0;
double   g_f_atr_pct       = 0;
double   g_f_rel_vol       = 0;
double   g_f_disp          = 0;
int      g_f_h1_bias       = 0;

//+------------------------------------------------------------------+
string DetectDE40Symbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true)) return InpSymbolOverride;
      Print("VWAPX: override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string candidates[] = {"GER40", "GER40.cash", "GER40+", "DE40", "DE40+",
                          "DAX40", "DAX", "Germany40", "DEU40", "DEU40.cash",
                          "GER40m", "GER40fs", "DAX.fs", "DE40fs"};
   for(int i = 0; i < ArraySize(candidates); i++)
      if(SymbolSelect(candidates[i], true))
         if(SymbolInfoDouble(candidates[i], SYMBOL_BID) > 0) return candidates[i];
   string cur = _Symbol; StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0) return _Symbol;
   return _Symbol;
}

void GmtTime(datetime t, MqlDateTime &dt)
{
   TimeToStruct((datetime)((long)t - (long)InpServerUTC * 3600), dt);
}

string SessionBucket(int gmtHour)
{
   if(gmtHour < 7)  return "Asia";
   if(gmtHour < 8)  return "Frankfurt";
   if(gmtHour < 11) return "London";
   if(gmtHour < 13) return "Midday";
   if(gmtHour < 16) return "USOverlap";
   return "Late";
}

double GetATR15()
{
   if(g_hATR15 == INVALID_HANDLE) return 0;
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(g_hATR15, 0, 1, 1, b) < 1) return 0;
   return b[0];
}

//+------------------------------------------------------------------+
//| Session VWAP: cumulative tick-volume-weighted price from 07:00 GMT |
//+------------------------------------------------------------------+
double ComputeVWAP()
{
   MqlDateTime nowdt; GmtTime(TimeCurrent(), nowdt);
   int y = nowdt.year, m = nowdt.mon, d = nowdt.day;
   MqlRates rates[];
   datetime from = (datetime)((long)TimeCurrent() - 24 * 3600);
   int got = CopyRates(g_activeSymbol, PERIOD_M15, from, TimeCurrent(), rates);
   if(got <= 1) return 0;
   double pv = 0, v = 0;
   MqlDateTime dt;
   for(int i = 0; i < got; i++)
   {
      GmtTime(rates[i].time, dt);
      if(dt.year == y && dt.mon == m && dt.day == d && dt.hour >= InpVwapStartGMT)
      {
         double typ = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
         pv += typ * (double)rates[i].tick_volume;
         v  += (double)rates[i].tick_volume;
      }
   }
   if(v <= 0) return 0;
   return pv / v;
}

//+------------------------------------------------------------------+
void ComputeForensics(double entryPrice, double atr15, double extLine)
{
   g_f_vwap_dist_atr = (atr15 > 0) ? (entryPrice - g_vwap) / atr15 : 0;
   g_f_vwap_ext_atr  = (atr15 > 0) ? (g_vwap - g_extExtreme) / atr15 : 0;
   g_f_reclaim_atr   = (atr15 > 0) ? (entryPrice - extLine) / atr15 : 0;

   g_f_price_ema200 = 0;
   if(g_hEMA200 != INVALID_HANDLE)
   {
      double eb[]; ArraySetAsSeries(eb, true);
      if(CopyBuffer(g_hEMA200, 0, 1, 1, eb) >= 1 && eb[0] > 0 && atr15 > 0)
         g_f_price_ema200 = (entryPrice - eb[0]) / atr15;
   }

   g_f_atr_pct = 0;
   if(g_hATR15 != INVALID_HANDLE)
   {
      double ab[]; ArraySetAsSeries(ab, true);
      int n = CopyBuffer(g_hATR15, 0, 1, 500, ab);
      if(n > 0)
      {
         int le = 0;
         for(int i = 0; i < n; i++) if(ab[i] <= atr15) le++;
         g_f_atr_pct = 100.0 * (double)le / (double)n;
      }
   }

   g_f_rel_vol = 0; g_f_disp = 0;
   MqlRates rb[];
   int nB = CopyRates(g_activeSymbol, PERIOD_M15, 0, 21, rb);
   if(nB >= 21)
   {
      double v20 = 0;
      for(int i = 1; i <= 20; i++) v20 += (double)rb[i].tick_volume;
      if(v20 > 0) g_f_rel_vol = (double)rb[1].tick_volume * 20.0 / v20;
      double maxBody = 0;
      for(int i = 1; i <= 3 && i < nB; i++)
      {
         double body = MathAbs(rb[i].close - rb[i].open);
         if(body > maxBody) maxBody = body;
      }
      if(atr15 > 0) g_f_disp = maxBody / atr15;
   }

   g_f_h1_bias = 0;
   double e20 = 0, e50 = 0;
   double b20[]; ArraySetAsSeries(b20, true);
   double b50[]; ArraySetAsSeries(b50, true);
   if(g_hEMA20H1 != INVALID_HANDLE && CopyBuffer(g_hEMA20H1, 0, 1, 1, b20) >= 1) e20 = b20[0];
   if(g_hEMA50H1 != INVALID_HANDLE && CopyBuffer(g_hEMA50H1, 0, 1, 1, b50) >= 1) e50 = b50[0];
   if(e20 > 0 && e50 > 0)
   {
      if(e20 > e50) g_f_h1_bias = 1;
      else if(e20 < e50) g_f_h1_bias = -1;
   }
}

//+------------------------------------------------------------------+
void TryEntry(double extLine)
{
   if(g_inPosition) return;
   if(!InpAllowLong) return;
   double atr15 = GetATR15();
   if(atr15 <= 0) return;
   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return;
   double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
   if(entry <= 0) return;
   double sl = NormalizeDouble(g_extExtreme - InpSLBufATR * atr15, _Digits);
   double risk = entry - sl;
   if(risk <= 0) return;
   double riskPts = risk / _Point;
   double tp = NormalizeDouble(entry + risk * InpTP_RR, _Digits);

   ComputeForensics(entry, atr15, extLine);

   if(InpGateDisp && g_f_disp < InpDispMin)
   {
      Print("VWAPX: GateDisp blocked | disp=", DoubleToString(g_f_disp, 3)); return;
   }

   double volStep = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MAX);
   double lots = InpLots;
   if(volStep > 0) lots = MathFloor(lots / volStep) * volStep;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;

   if(!trade.Buy(lots, g_activeSymbol, entry, sl, tp, "VWAPX_EXT_REVERT_LONG"))
   {
      Print("VWAPX: order failed | err=", GetLastError());
      return;
   }
   double fill = trade.ResultPrice();
   g_inPosition  = true;
   g_posDir      = +1;
   g_entryPrice  = (fill > 0) ? fill : entry;
   g_sl          = sl;
   g_tp          = tp;
   g_riskPts     = riskPts;
   g_mfeR        = 0;
   g_maeR        = 0;
   g_entryTime   = TimeCurrent();

   MqlDateTime dt; GmtTime(g_entryTime, dt);
   g_entryDow     = dt.day_of_week;
   g_entryHour    = dt.hour;
   g_entrySession = SessionBucket(dt.hour);

   Print("VWAPX_EXT_REVERT_LONG | entry=", DoubleToString(g_entryPrice, _Digits),
         " | sl=", DoubleToString(sl, _Digits), " | tp=", DoubleToString(tp, _Digits),
         " | vwap=", DoubleToString(g_vwap, _Digits),
         " | extExt=", DoubleToString(g_extExtreme, _Digits),
         " | extDepth=", DoubleToString(g_f_vwap_ext_atr, 3));
}

//+------------------------------------------------------------------+
void EvaluateNewBar()
{
   double close = iClose(g_activeSymbol, PERIOD_M15, 1);
   double low   = iLow(g_activeSymbol, PERIOD_M15, 1);
   if(close <= 0) return;
   double atr15 = GetATR15();
   if(atr15 <= 0) return;
   double vwap = ComputeVWAP();
   if(vwap <= 0) return;
   g_vwap = vwap;
   double extLine = vwap - InpVwapExtATR * atr15;

   if(g_entryDoneForDay) return;

   if(!g_extActive)
   {
      if(low <= extLine) { g_extActive = true; g_extExtreme = low; }
      else return;
   }

   if(low < g_extExtreme) g_extExtreme = low;
   if(close > extLine)                          // extension exhausted -> reclaim -> long
   {
      g_extActive = false;
      g_entryDoneForDay = true;
      MqlDateTime dt; GmtTime(iTime(g_activeSymbol, PERIOD_M15, 1), dt);
      if(dt.hour >= InpEntryStartGMT && dt.hour < InpEntryEndGMT)
         TryEntry(extLine);
   }
}

//+------------------------------------------------------------------+
bool FindExitDeal(double &price, datetime &time)
{
   price = 0; time = 0;
   if(!HistorySelect(g_entryTime, TimeCurrent() + 120)) return false;
   int n = HistoryDealsTotal();
   for(int i = n - 1; i >= 0; i--)
   {
      ulong dticket = HistoryDealGetTicket(i);
      if(dticket == 0) continue;
      if(HistoryDealGetString(dticket, DEAL_SYMBOL) != g_activeSymbol) continue;
      if(HistoryDealGetInteger(dticket, DEAL_MAGIC) != (long)InpMagic) continue;
      ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dticket, DEAL_ENTRY);
      if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_INOUT)
      {
         price = HistoryDealGetDouble(dticket, DEAL_PRICE);
         time  = (datetime)HistoryDealGetInteger(dticket, DEAL_TIME);
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
void LogTradeClose(double exitPrice, datetime exitTime)
{
   if(g_entryPrice <= 0 || g_riskPts <= 0) return;
   double profitPts = (exitPrice - g_entryPrice) / _Point;
   double R = profitPts / g_riskPts;
   string fname = StringFormat("DE40X1_TRADES_%d.csv", InpMagic);

   int h = FileOpen(fname, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   bool needHeader = false;
   if(h == INVALID_HANDLE)
   {
      h = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      needHeader = true;
   }
   else { FileSeek(h, 0, SEEK_END); needHeader = (FileSize(h) <= 0); }
   if(h == INVALID_HANDLE) { Print("VWAPX: cannot open CSV ", fname); return; }

   if(needHeader)
      FileWrite(h, "time_open", "time_close", "side", "entry", "sl", "tp",
                "exit_price", "R", "MFE_R", "MAE_R", "module", "gmt_hour",
                "weekday", "session_bucket", "vwap_dist_atr", "vwap_ext_atr",
                "reclaim_atr", "f_price_ema200", "f_atr_pct", "f_rel_vol",
                "f_disp", "f_h1_bias");

   FileWrite(h, (long)g_entryTime, (long)exitTime, "BUY",
             DoubleToString(g_entryPrice, _Digits), DoubleToString(g_sl, _Digits),
             DoubleToString(g_tp, _Digits), DoubleToString(exitPrice, _Digits),
             DoubleToString(R, 4), DoubleToString(g_mfeR, 4), DoubleToString(g_maeR, 4),
             "VWAPX", g_entryHour, g_entryDow, g_entrySession,
             DoubleToString(g_f_vwap_dist_atr, 4), DoubleToString(g_f_vwap_ext_atr, 4),
             DoubleToString(g_f_reclaim_atr, 4), DoubleToString(g_f_price_ema200, 4),
             DoubleToString(g_f_atr_pct, 4), DoubleToString(g_f_rel_vol, 4),
             DoubleToString(g_f_disp, 4), g_f_h1_bias);
   FileClose(h);

   Print("VWAPX: trade logged | exit=", DoubleToString(exitPrice, _Digits),
         " | R=", DoubleToString(R, 3), " | MFE=", DoubleToString(g_mfeR, 3),
         " | MAE=", DoubleToString(g_maeR, 3));
}

void ResetPosState()
{
   g_inPosition = false; g_posDir = 0;
   g_entryPrice = 0; g_sl = 0; g_tp = 0; g_riskPts = 0;
   g_mfeR = 0; g_maeR = 0;
   g_entryTime = 0; g_entryDow = 0; g_entryHour = 0; g_entrySession = "";
   g_f_vwap_dist_atr = 0; g_f_vwap_ext_atr = 0; g_f_reclaim_atr = 0;
   g_f_price_ema200 = 0; g_f_atr_pct = 0; g_f_rel_vol = 0; g_f_disp = 0; g_f_h1_bias = 0;
}

void ManagePosition()
{
   if(!g_inPosition) return;
   ulong openTk = 0; bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_activeSymbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) == (long)InpMagic) { found = true; openTk = tk; break; }
   }
   if(!found)
   {
      double exitPrice = 0; datetime exitTime = 0;
      if(!FindExitDeal(exitPrice, exitTime)) return;
      LogTradeClose(exitPrice, exitTime);
      ResetPosState();
      return;
   }
   double cur = SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
   if(cur <= 0 || g_riskPts <= 0) return;
   double r = (cur - g_entryPrice) / _Point / g_riskPts;
   if(r > g_mfeR) g_mfeR = r;
   if(r < g_maeR) g_maeR = r;
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_activeSymbol = DetectDE40Symbol();
   if(!SymbolSelect(g_activeSymbol, true)) return INIT_FAILED;
   g_hATR15   = iATR(g_activeSymbol, PERIOD_M15, 14);
   g_hEMA200  = iMA(g_activeSymbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hEMA20H1 = iMA(g_activeSymbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEMA50H1 = iMA(g_activeSymbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   if(g_hATR15 == INVALID_HANDLE) return INIT_FAILED;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   g_attachTime = TimeCurrent();
   g_lastM15 = 0;
   g_lastD1  = iTime(g_activeSymbol, PERIOD_D1, 0);
   g_extActive = false; g_entryDoneForDay = false; g_extExtreme = 0; g_vwap = 0;
   ResetPosState();

   Print("=== DE40 X1X Module 2 VWAPX v1.00 (magic ", InpMagic, ") ===");
   Print("VWAP anchor ", InpVwapStartGMT, " GMT | ext ", DoubleToString(InpVwapExtATR, 2),
         " ATR | entry ", InpEntryStartGMT, "-", InpEntryEndGMT, " | SLBuf ",
         DoubleToString(InpSLBufATR, 2), " ATR | long-only");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hATR15   != INVALID_HANDLE) IndicatorRelease(g_hATR15);
   if(g_hEMA200  != INVALID_HANDLE) IndicatorRelease(g_hEMA200);
   if(g_hEMA20H1 != INVALID_HANDLE) IndicatorRelease(g_hEMA20H1);
   if(g_hEMA50H1 != INVALID_HANDLE) IndicatorRelease(g_hEMA50H1);
}

void OnTick()
{
   ManagePosition();
   if(g_inPosition) return;
   if(TimeCurrent() - g_attachTime < InpColdStartSec) return;

   datetime d1Open = iTime(g_activeSymbol, PERIOD_D1, 0);
   if(d1Open != g_lastD1)
   {
      g_lastD1 = d1Open;
      g_extActive = false; g_entryDoneForDay = false; g_extExtreme = 0; g_vwap = 0;
   }

   datetime m15 = iTime(g_activeSymbol, PERIOD_M15, 1);
   if(m15 <= 0 || m15 == g_lastM15) return;
   g_lastM15 = m15;

   MqlDateTime dt; GmtTime(TimeCurrent(), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6) return;

   EvaluateNewBar();
}
//+------------------------------------------------------------------+