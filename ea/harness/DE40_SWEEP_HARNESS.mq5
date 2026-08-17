//+------------------------------------------------------------------+
//| DE40_SWEEP_HARNESS.mq5                                            |
//| Standalone research harness — SWEEP (Asia liquidity sweep +      |
//| reclaim reversal at Frankfurt open) for DE40 (Germany 40 / DAX)  |
//| on M15. Magic base: 4600.                                         |
//| CSV: DE40X1_TRADES_4600.csv (terminal Files dir).                |
//|                                                                    |
//| Logic (M15 closed bars; entries at bar open):                      |
//|   asia range = high/low of 00:00-07:00 GMT (InpAsiaStartGMT/End)  |
//|   sweep      = in 07:00-10:00 GMT (InpSweepStartGMT/End), price   |
//|                trades beyond asia high (short setup) or below     |
//|                asia low (long setup) by <= InpMaxSweepATR x       |
//|                ATR14(M15)                                         |
//|   reclaim    = a completed M15 bar closes back inside the asia    |
//|                range after the sweep                              |
//|   entry      = on that confirmation close; direction = fade the   |
//|                sweep (up-sweep -> short, down-sweep -> long)      |
//|   SL         = sweep extreme +/- InpSLBufATR x ATR                |
//|   TP         = fixed RR (InpTpRR) or opposite Asia edge (enum)    |
//|   one trade per day; one position; optional EMA trend gate (OFF)  |
//|   spread guard; per-trade CSV + MFE/MAE per tick                  |
//|                                                                    |
//| CSV columns: time_open,time_close,side,entry,sl,tp,exit_price,    |
//|   R,MFE_R,MAE_R,module,weekday,gmt_hour,session_bucket,comment    |
//| weekday: MQL5 day_of_week (0=Sun .. 6=Sat).                       |
//| session_bucket (GMT): 0=00-06 Asia/pre, 1=07 Frankfurt open,      |
//|   2=08-10 London/Xetra morning, 3=11-12:29 London mid,            |
//|   4=12:30-13:59 news window, 5=14-15 US overlap, 6=16-23 late.    |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 SWEEP — Asia liquidity sweep + reclaim reversal, fade (M15)"

#include <Trade\Trade.mqh>
CTrade trade;

//+------------------------------------------------------------------+
//| ENUMS                                                            |
//+------------------------------------------------------------------+
enum ENUM_SWEEP_TP
{
   TP_FIXED_RR  = 0,  // Fixed reward:risk (InpTpRR)
   TP_ASIA_EDGE = 1   // Opposite Asia range edge
};

//+------------------------------------------------------------------+
//| INPUTS                                                           |
//+------------------------------------------------------------------+
input group "=== Symbol & Time ==="
input string InpSymbolOverride = "";   // Override symbol (empty = auto-detect)
input int    InpServerUTC      = 2;    // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== Asia Range (GMT) ==="
input int    InpAsiaStartGMT   = 0;    // Asia range start hour GMT
input int    InpAsiaEndGMT     = 7;    // Asia range end hour GMT

input group "=== Sweep & Reclaim (GMT) ==="
input int    InpSweepStartGMT  = 7;    // Sweep window start hour GMT
input int    InpSweepEndGMT    = 10;   // Sweep window end hour GMT
input double InpMaxSweepATR    = 1.0;  // Max sweep distance x ATR14 (0.3-2.0)

input group "=== Trend Gate (ablation; OFF for fade family) ==="
input bool   InpUseTrendGate   = false; // Ablation: false = no EMA trend gate
input int    InpTrendEmaPeriod = 200;  // Trend EMA period
input int    InpTrendSlopeBars = 5;    // EMA slope lookback bars for sign

input group "=== Stops & Targets ==="
input int    InpAtrPeriod      = 14;   // ATR period (M15)
input double InpSLBufATR       = 0.3;  // SL buffer beyond sweep extreme x ATR
input double InpTpRR           = 1.0;  // Fixed TP reward:risk (0.8-1.5)
input ENUM_SWEEP_TP InpTpMode  = TP_FIXED_RR; // TP mode: fixed RR | opposite edge

input group "=== Direction Filters ==="
input bool   InpAllowLong      = true;  // allow long entries (fade down-sweep)
input bool   InpAllowShort     = true;  // allow short entries (fade up-sweep)

input group "=== Risk & Safety ==="
input double InpRiskPct        = 1.0;  // Risk per trade (% of balance)
input int    InpMaxSpreadPts   = 500;  // Max spread (points) to allow entry
input int    InpMagic          = 4600; // Expert magic number (SWEEP base)
input int    InpMaxTradesDay   = 1;    // Daily trade governor (one trade per day)

//+------------------------------------------------------------------+
//| CONSTANTS & GLOBALS                                              |
//+------------------------------------------------------------------+
#define ST_IDLE    0
#define ST_SWEEP   1
#define ST_RECLAIM 2

// Setup state (asia range -> sweep -> reclaim)
int      g_state         = ST_IDLE;
double   g_asiaHi        = 0;       // Asia range high (00:00-07:00 GMT)
double   g_asiaLo        = 0;       // Asia range low
int      g_sweepDir      = 0;       // +1 long fade, -1 short fade
double   g_sweepExtreme  = 0;       // highest high (short) / lowest low (long)

// Position state (single position, magic 4600)
bool     g_inPosition = false;
datetime g_entryTime  = 0;
double   g_entryPrice = 0;
double   g_sl         = 0;
double   g_tp         = 0;
double   g_riskAmount = 0;
int      g_tradeDir   = 0;
double   g_mfeR       = 0;           // max favorable excursion (R)
double   g_minProfitR = 0;           // min profit R seen (may be negative) -> MAE
double   g_maeR       = 0;           // realized max adverse excursion (R, positive)
int      g_entryWeekday  = 0;
int      g_entryGmtHour  = 0;
int      g_entrySession  = 0;

// Daily / bar context
datetime g_lastBar      = 0;
long     g_gmtDayKey    = 0;         // YYYYMMDD (GMT) for daily reset
int      g_tradesToday  = 0;

string   g_symbol  = "";
string   g_logFile = "";
int      g_digits  = 0;

int      g_hATR = INVALID_HANDLE;
int      g_hEMA = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Symbol auto-detection                                             |
//+------------------------------------------------------------------+
string DetectSymbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("SWEEP: override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string cand[] = {
      "GER40", "GER40.s", "GER40.cash", "GER40+", "GER40ft", "GER40m",
      "DE40", "DE40+", "DAX40", "DAX", "Germany40", "DEU40", "DEU40.cash", "DAX.fs"
   };
   for(int i = 0; i < ArraySize(cand); i++)
   {
      if(SymbolSelect(cand[i], true))
      {
         if(SymbolInfoDouble(cand[i], SYMBOL_BID) > 0)
         {
            Print("SWEEP: detected symbol ", cand[i]);
            return cand[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("SWEEP: WARNING - no DE40 symbol found, using chart symbol ", _Symbol);
   return _Symbol;
}

//+------------------------------------------------------------------+
//| GMT helpers (all session logic in GMT via InpServerUTC)           |
//+------------------------------------------------------------------+
void ComputeGmt(datetime t, int &weekday, int &gmtHour, int &gmtMinOfDay)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   weekday = dt.day_of_week;
   int h = dt.hour - InpServerUTC;
   while(h < 0)  h += 24;
   while(h >= 24) h -= 24;
   gmtHour = h;
   gmtMinOfDay = h * 60 + dt.min;
}

// GMT YYYYMMDD key for daily rollover (offset-aware via InpServerUTC)
long GmtDayKey(datetime t)
{
   datetime gmt = t - (datetime)(InpServerUTC * 3600);
   MqlDateTime dt;
   TimeToStruct(gmt, dt);
   return (long)dt.year * 10000 + (long)dt.mon * 100 + (long)dt.day;
}

// GMT minute-of-day for a given (bar) server timestamp
int GmtMinOfDayOf(datetime t)
{
   int wd, gh, gmo;
   ComputeGmt(t, wd, gh, gmo);
   return gmo;
}

// Session bucket (GMT). See header comment for legend.
int SessionBucket(int gmtMin)
{
   if(gmtMin < 7 * 60)       return 0;  // 00:00-06:59 Asia/pre
   if(gmtMin < 8 * 60)       return 1;  // 07:00-07:59 Frankfurt open
   if(gmtMin < 11 * 60)      return 2;  // 08:00-10:59 London/Xetra morning
   if(gmtMin < 12 * 60 + 30) return 3;  // 11:00-12:29 London mid
   if(gmtMin < 14 * 60)      return 4;  // 12:30-13:59 news window
   if(gmtMin < 16 * 60)      return 5;  // 14:00-15:59 US overlap
   return 6;                            // 16:00-23:59 late
}

//+------------------------------------------------------------------+
//| Indicator helpers                                                 |
//+------------------------------------------------------------------+
double GetATR()
{
   if(g_hATR == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hATR, 0, 1, 2, buf) < 2) return 0;
   return buf[0];   // shift 1 (last closed M15 bar)
}

bool TrendGatePass(int dir)
{
   if(!InpUseTrendGate) return true;
   if(g_hEMA == INVALID_HANDLE) return false;
   int need = InpTrendSlopeBars + 1;
   double ema[];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(g_hEMA, 0, 1, need, ema) < need) return false;
   double emaNow  = ema[0];                      // shift 1
   double emaThen = ema[InpTrendSlopeBars];      // shift 1 + slopeBars
   double slope   = emaNow - emaThen;
   double c1      = iClose(g_symbol, PERIOD_M15, 1);
   if(dir == 1)
   {
      if(c1 <= emaNow) return false;   // price not above EMA
      if(slope <= 0)   return false;   // EMA not rising
   }
   else
   {
      if(c1 >= emaNow) return false;   // price not below EMA
      if(slope >= 0)   return false;   // EMA not falling
   }
   return true;
}

//+------------------------------------------------------------------+
//| Lot sizing from fixed risk %                                      |
//+------------------------------------------------------------------+
double CalcLots(double risk)
{
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;
   double tickVal   = SymbolInfoDouble(g_symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(g_symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || risk <= 0) return 0;
   double lots = riskMoney / (risk / tickSize * tickVal);
   double minLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);
   if(lotStep <= 0) lotStep = 0.01;
   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);
   return lots;
}

//+------------------------------------------------------------------+
//| Setup lifecycle                                                   |
//+------------------------------------------------------------------+
void ResetSetup()
{
   g_state         = ST_IDLE;
   g_asiaHi        = 0;
   g_asiaLo        = 0;
   g_sweepDir      = 0;
   g_sweepExtreme  = 0;
}

// Compute the Asia range (high/low of completed M15 bars whose open
// time falls in [InpAsiaStartGMT, InpAsiaEndGMT) of refTime's GMT day).
void ComputeAsiaRange(datetime refTime, double &hi, double &lo)
{
   hi = 0;
   lo = 0;
   long refDay = GmtDayKey(refTime);
   int asiaStartMin = InpAsiaStartGMT * 60;
   int asiaEndMin   = InpAsiaEndGMT * 60;
   // 60 bars = 15h: comfortably covers 00:00-07:00 behind a 07:00 ref bar.
   for(int i = 1; i <= 60; i++)
   {
      datetime bt = iTime(g_symbol, PERIOD_M15, i);
      if(bt == 0) continue;
      if(GmtDayKey(bt) != refDay) continue;
      int gmo = GmtMinOfDayOf(bt);
      if(gmo < asiaStartMin || gmo >= asiaEndMin) continue;
      double h = iHigh(g_symbol, PERIOD_M15, i);
      double l = iLow(g_symbol, PERIOD_M15, i);
      if(h <= 0 || l <= 0) continue;
      if(lo <= 0 || l < lo) lo = l;
      if(h > hi) hi = h;
   }
}

//+------------------------------------------------------------------+
//| Sweep + reclaim state machine (runs on new M15 bar)               |
//+------------------------------------------------------------------+
void RunEngine()
{
   double c1 = iClose(g_symbol, PERIOD_M15, 1);
   double h1 = iHigh(g_symbol, PERIOD_M15, 1);
   double l1 = iLow(g_symbol, PERIOD_M15, 1);
   datetime t1 = iTime(g_symbol, PERIOD_M15, 1);
   if(c1 <= 0 || h1 <= 0 || l1 <= 0 || t1 == 0) return;

   int gmo = GmtMinOfDayOf(t1);
   int sweepStartMin = InpSweepStartGMT * 60;
   int sweepEndMin   = InpSweepEndGMT * 60;
   bool inSweep = (gmo >= sweepStartMin && gmo < sweepEndMin);

   if(g_state == ST_IDLE)
   {
      if(!inSweep) return;              // before sweep window (asia/pre) or after
      ComputeAsiaRange(t1, g_asiaHi, g_asiaLo);
      if(g_asiaHi <= 0 || g_asiaLo <= 0 || g_asiaHi <= g_asiaLo)
      {
         // No valid Asia range -> cannot define a sweep today.
         g_asiaHi = 0;
         g_asiaLo = 0;
         return;
      }
      g_state = ST_SWEEP;
   }

   // From here g_state is ST_SWEEP or ST_RECLAIM.
   if(!inSweep) { ResetSetup(); return; }   // window ended without entry

   double atr = GetATR();
   if(atr <= 0) return;
   double maxSweep = InpMaxSweepATR * atr;

   if(g_state == ST_SWEEP)
   {
      double upExt = h1 - g_asiaHi;   // >0 => price traded above asia high
      double dnExt = g_asiaLo - l1;   // >0 => price traded below asia low
      bool upOk = (upExt > 0 && upExt <= maxSweep);
      bool dnOk = (dnExt > 0 && dnExt <= maxSweep);

      if(upOk)
      {
         g_sweepDir     = -1;   // fade up-sweep -> SHORT
         g_sweepExtreme = h1;
         g_state        = ST_RECLAIM;
      }
      else if(dnOk)
      {
         g_sweepDir     = 1;    // fade down-sweep -> LONG
         g_sweepExtreme = l1;
         g_state        = ST_RECLAIM;
      }
   }

   if(g_state == ST_RECLAIM)
   {
      // Track sweep extreme (may extend on later bars within the window).
      if(g_sweepDir == -1)
      {
         if(h1 > g_sweepExtreme)
         {
            if((h1 - g_asiaHi) <= maxSweep)
               g_sweepExtreme = h1;
            else { ResetSetup(); return; }   // sweep blew past max -> invalidate
         }
      }
      else
      {
         if(l1 < g_sweepExtreme)
         {
            if((g_asiaLo - l1) <= maxSweep)
               g_sweepExtreme = l1;
            else { ResetSetup(); return; }
         }
      }

      // Reclaim: completed bar closes back inside the Asia range.
      if(c1 >= g_asiaLo && c1 <= g_asiaHi)
      {
         TryEntry(g_sweepDir);
         ResetSetup();
      }
   }
}

//+------------------------------------------------------------------+
//| Entry                                                             |
//+------------------------------------------------------------------+
void TryEntry(int dir)
{
   if(dir == 1 && !InpAllowLong)   return;
   if(dir == -1 && !InpAllowShort) return;

   long spread = SymbolInfoInteger(g_symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return;

   if(!TrendGatePass(dir)) return;

   double atr = GetATR();
   if(atr <= 0) return;

   double entry = (dir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(g_symbol, SYMBOL_BID);

   // SL beyond sweep extreme + buffer.
   double sl = (dir == 1) ? g_sweepExtreme - InpSLBufATR * atr
                          : g_sweepExtreme + InpSLBufATR * atr;
   double risk = (dir == 1) ? entry - sl : sl - entry;
   if(risk <= 0) return;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   // TP: fixed RR or opposite Asia edge.
   double tp;
   if(InpTpMode == TP_FIXED_RR)
      tp = (dir == 1) ? entry + risk * InpTpRR : entry - risk * InpTpRR;
   else
      tp = (dir == 1) ? g_asiaHi : g_asiaLo;   // opposite Asia edge

   // Fall back to fixed RR if the chosen TP is not profitably beyond entry.
   if((dir == 1 && tp <= entry) || (dir == -1 && tp >= entry))
      tp = (dir == 1) ? entry + risk * InpTpRR : entry - risk * InpTpRR;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   string comment = "SWEEP_" + ((dir == 1) ? "L" : "S");
   trade.SetExpertMagicNumber(InpMagic);
   bool ok = (dir == 1) ? trade.Buy(lots, g_symbol, entry, sl, tp, comment)
                        : trade.Sell(lots, g_symbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("SWEEP_ENTRY_REJECTED | ", comment, " | ret=", trade.ResultRetcode());
      return;
   }

   g_inPosition  = true;
   g_entryTime   = TimeCurrent();
   g_entryPrice  = (trade.ResultPrice() > 0) ? trade.ResultPrice() : entry;
   g_sl          = sl;
   g_tp          = tp;
   g_riskAmount  = risk;
   g_tradeDir    = dir;
   g_mfeR        = 0;
   g_minProfitR  = 0;
   g_tradesToday++;

   int wd, gh, gmo;
   ComputeGmt(g_entryTime, wd, gh, gmo);
   g_entryWeekday = wd;
   g_entryGmtHour = gh;
   g_entrySession = SessionBucket(gmo);

   Print("SWEEP_TRADE | ", g_symbol, " | ", (dir == 1 ? "BUY" : "SELL"),
         " | lots=", DoubleToString(lots, 2),
         " | entry=", DoubleToString(g_entryPrice, g_digits),
         " | sl=", DoubleToString(sl, g_digits),
         " | tp=", DoubleToString(tp, g_digits),
         " | risk=", DoubleToString(risk, g_digits),
         " | R=", DoubleToString(risk / atr, 2), " ATR",
         " | sess=", IntegerToString(g_entrySession));
}

//+------------------------------------------------------------------+
//| Live position tracking: MFE/MAE per tick + close detection        |
//+------------------------------------------------------------------+
void ManagePosition()
{
   if(!g_inPosition) return;

   bool stillOpen = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      stillOpen = true;
      break;
   }

   if(stillOpen && g_riskAmount > 0 && g_tradeDir != 0)
   {
      double cur = (g_tradeDir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_BID)
                                     : SymbolInfoDouble(g_symbol, SYMBOL_ASK);
      double profitR = (g_tradeDir == 1) ? (cur - g_entryPrice) / g_riskAmount
                                         : (g_entryPrice - cur) / g_riskAmount;
      if(profitR > g_mfeR)       g_mfeR = profitR;
      if(profitR < g_minProfitR) g_minProfitR = profitR;
      return;
   }

   // position closed -> finalize
   double   exitPrice = 0;
   datetime closeTime = 0;
   HistorySelect(g_entryTime - 60, TimeCurrent() + 60);
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      ulong dk = HistoryDealGetTicket(i);
      if(dk == 0) continue;
      if(HistoryDealGetString(dk, DEAL_SYMBOL) != g_symbol) continue;
      if((int)HistoryDealGetInteger(dk, DEAL_MAGIC) != InpMagic) continue;
      long entry = HistoryDealGetInteger(dk, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT || entry == DEAL_ENTRY_OUT_BY)
      {
         exitPrice = HistoryDealGetDouble(dk, DEAL_PRICE);
         closeTime = (datetime)HistoryDealGetInteger(dk, DEAL_TIME);
      }
   }
   if(exitPrice <= 0)
   {
      exitPrice = (g_tradeDir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_BID)
                                    : SymbolInfoDouble(g_symbol, SYMBOL_ASK);
      closeTime = TimeCurrent();
   }

   double R = (g_riskAmount > 0)
              ? ((g_tradeDir == 1) ? (exitPrice - g_entryPrice) / g_riskAmount
                                   : (g_entryPrice - exitPrice) / g_riskAmount)
              : 0;
   g_maeR = (g_minProfitR < 0) ? -g_minProfitR : 0;

   WriteTradeLog(closeTime, exitPrice, R);

   Print("SWEEP_CLOSE | ", (g_tradeDir == 1) ? "BUY" : "SELL",
         " | exit=", DoubleToString(exitPrice, g_digits),
         " | R=", DoubleToString(R, 3),
         " | MFE=", DoubleToString(g_mfeR, 3),
         " | MAE=", DoubleToString(g_maeR, 3));

   g_inPosition = false;
   g_entryTime  = 0;
   g_entryPrice = 0;
   g_sl         = 0;
   g_tp         = 0;
   g_riskAmount = 0;
   g_tradeDir   = 0;
   g_mfeR       = 0;
   g_minProfitR = 0;
   g_maeR       = 0;
}

//+------------------------------------------------------------------+
//| Per-trade CSV log (terminal Files dir)                            |
//+------------------------------------------------------------------+
void WriteTradeLog(datetime closeTime, double exitPrice, double R)
{
   bool exists = FileIsExist(g_logFile, FILE_COMMON);
   int handle = INVALID_HANDLE;

   if(!exists)
   {
      handle = FileOpen(g_logFile, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      if(handle == INVALID_HANDLE) return;
      FileWrite(handle,
                "time_open", "time_close", "side", "entry", "sl", "tp", "exit_price",
                "R", "MFE_R", "MAE_R", "module", "weekday", "gmt_hour",
                "session_bucket", "comment");
   }
   else
   {
      handle = FileOpen(g_logFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      if(handle == INVALID_HANDLE) return;
      FileSeek(handle, 0, SEEK_END);
   }

   FileWrite(handle,
             TimeToString(g_entryTime, TIME_DATE | TIME_SECONDS),
             TimeToString(closeTime, TIME_DATE | TIME_SECONDS),
             (g_tradeDir == 1) ? "BUY" : "SELL",
             DoubleToString(g_entryPrice, g_digits),
             DoubleToString(g_sl, g_digits),
             DoubleToString(g_tp, g_digits),
             DoubleToString(exitPrice, g_digits),
             DoubleToString(R, 4),
             DoubleToString(g_mfeR, 4),
             DoubleToString(g_maeR, 4),
             "SWEEP",
             IntegerToString(g_entryWeekday),
             IntegerToString(g_entryGmtHour),
             IntegerToString(g_entrySession),
             "SWEEP_" + ((g_tradeDir == 1) ? "L" : "S"));
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Expert initialization / deinitialization                          |
//+------------------------------------------------------------------+
int OnInit()
{
   g_symbol = DetectSymbol();
   if(!SymbolSelect(g_symbol, true))
   {
      Print("SWEEP: FATAL - cannot select symbol ", g_symbol);
      return INIT_FAILED;
   }
   g_digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);

   g_hATR = iATR(g_symbol, PERIOD_M15, InpAtrPeriod);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("SWEEP: FATAL - ATR handle failed");
      return INIT_FAILED;
   }
   if(InpUseTrendGate)
   {
      g_hEMA = iMA(g_symbol, PERIOD_M15, InpTrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hEMA == INVALID_HANDLE)
      {
         Print("SWEEP: FATAL - trend EMA handle failed");
         return INIT_FAILED;
      }
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_logFile     = StringFormat("DE40X1_TRADES_%d.csv", InpMagic);
   g_lastBar     = 0;
   g_gmtDayKey   = 0;
   g_tradesToday = 0;
   ResetSetup();

   Print("=== DE40 SWEEP Harness v1.00 ===");
   Print("Symbol: ", g_symbol, " | Magic: ", InpMagic, " | TF: M15 | log: ", g_logFile);
   Print("Asia: ", InpAsiaStartGMT, ":00-", InpAsiaEndGMT, ":00 GMT");
   Print("Sweep: ", InpSweepStartGMT, ":00-", InpSweepEndGMT, ":00 GMT | MaxSweep: ",
         DoubleToString(InpMaxSweepATR, 2), " x ATR");
   Print("SLBuf: ", DoubleToString(InpSLBufATR, 2), " x ATR | TP RR: ",
         DoubleToString(InpTpRR, 2), " | TP mode: ",
         (InpTpMode == TP_FIXED_RR ? "fixed RR" : "opposite edge"));
   Print("TrendGate: ", InpUseTrendGate ? "ON" : "OFF",
         " | EMA: ", InpTrendEmaPeriod, " | SlopeBars: ", InpTrendSlopeBars);
   Print("AllowLong: ", InpAllowLong, " | AllowShort: ", InpAllowShort,
         " | MaxTradesDay: ", InpMaxTradesDay);
   Print("Spread: ", SymbolInfoInteger(g_symbol, SYMBOL_SPREAD),
         " pts | Digits: ", g_digits);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hATR != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hEMA != INVALID_HANDLE) IndicatorRelease(g_hEMA);
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   ManagePosition();   // per-tick: MFE/MAE + close detection

   datetime curBar = iTime(g_symbol, PERIOD_M15, 0);
   if(curBar == 0 || curBar == g_lastBar) return;
   g_lastBar = curBar;

   if(g_inPosition) return;   // one position at a time

   int wd, gh, gmo;
   ComputeGmt(TimeCurrent(), wd, gh, gmo);
   if(wd == 0 || wd == 6) { ResetSetup(); return; }   // weekend

   long dayKey = GmtDayKey(TimeCurrent());
   if(dayKey != g_gmtDayKey)
   {
      g_gmtDayKey   = dayKey;
      g_tradesToday = 0;
      ResetSetup();
   }

   if(g_tradesToday >= InpMaxTradesDay) return;   // one trade per day

   RunEngine();
}
//+------------------------------------------------------------------+
