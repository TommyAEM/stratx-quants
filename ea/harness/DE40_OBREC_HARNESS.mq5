//+------------------------------------------------------------------+
//| DE40_OBREC_HARNESS.mq5                                            |
//| Standalone Order-Block Reclamation research harness for DE40      |
//| (Germany 40 / DAX). Single self-contained module, magic 4300.     |
//|                                                                    |
//| Strategy (per supervisor plan step 9):                             |
//|   - Order block = last opposite-direction candle before an        |
//|     impulse move (impulse body >= InpImpulseMult x ATR14 on M15). |
//|   - OB zone = body range [min(o,c) .. max(o,c)] of that candle.   |
//|   - Reclamation = price sweeps "through" the zone, then closes    |
//|     back beyond the far edge for InpConfirmCloses consecutive     |
//|     M15 bars; entry on that confirmation close.                   |
//|   - Direction = impulse direction.                                |
//|   - SL beyond the zone + 0.3 ATR buffer; TP = fixed RR.           |
//|   - Optional EMA200 slope agreement gate (trend filter).           |
//|   - One position only; spread guard; per-trade CSV + MFE/MAE.     |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 OBREC — Order-Block Reclamation (M15)"

#include <Trade\Trade.mqh>
CTrade trade;

//+------------------------------------------------------------------+
//| INPUTS                                                            |
//+------------------------------------------------------------------+
input group "=== Symbol & Time ==="
input string InpSymbolOverride = "";   // Override symbol (empty=auto-detect)
input int    InpServerUTC      = 2;    // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== OB Reclamation Core ==="
input double InpImpulseMult    = 1.4;  // Impulse body >= this x ATR14 (range 1.0-2.0)
input int    InpMaxOBage       = 30;   // Max OB age in M15 bars (range 10-60)
input int    InpConfirmCloses  = 2;    // Consecutive closes beyond far edge (range 1-5)
input double InpTP_RR          = 1.0;  // Fixed reward:risk take-profit (range 0.8-1.5)

input group "=== Trend Filter ==="
input bool   InpTrendGate      = true; // EMA200 slope must agree with trade direction
input bool   InpAllowLong      = true; // allow long entries
input bool   InpAllowShort     = true; // allow short entries

input group "=== Risk & Safety ==="
input double InpRiskPct        = 0.5;  // Risk per trade (% of balance)
input int    InpMaxSpreadPts   = 500;  // Max spread in points (spread guard)
input int    InpMagic          = 4300; // Expert magic number

//+------------------------------------------------------------------+
//| CONSTANTS                                                         |
//+------------------------------------------------------------------+
#define ATR_PERIOD        14     // ATR14 (M15)
#define TREND_EMA_PERIOD  200    // EMA200
#define TREND_SLOPE_LB    5      // slope lookback (M15 bars)
#define SL_BUFFER_ATR     0.3    // stop-loss buffer beyond zone (ATR)

//+------------------------------------------------------------------+
//| WORKING STATE (clamped copies of ranged inputs)                    |
//+------------------------------------------------------------------+
double g_impulseMult   = 1.4;
int    g_maxObAge      = 30;
int    g_confirmCloses = 2;
double g_tpRR          = 1.0;

//+------------------------------------------------------------------+
//| RUNTIME STATE                                                     |
//+------------------------------------------------------------------+
string   g_symbol       = "";
int      g_digits       = 0;
int      g_hATR         = INVALID_HANDLE;
int      g_hEMA         = INVALID_HANDLE;
string   g_logFile      = "";

// OB detection state
bool     g_armed        = false;
int      g_obDir        = 0;     // +1 long, -1 short (impulse direction)
double   g_obZoneHigh   = 0;
double   g_obZoneLow    = 0;
datetime g_obBarTime    = 0;
int      g_obAgeBars    = 0;
bool     g_mitigated    = false; // price swept "through" the zone
int      g_confirmCount = 0;     // consecutive closes beyond far edge
datetime g_lastObTime   = 0;     // OB already consumed (prevents re-trade)

datetime g_lastBarTime  = 0;

// Position state (single position, magic 4300)
bool     g_inPosition   = false;
int      g_tradeDir     = 0;
double   g_entryPrice   = 0;
double   g_sl           = 0;
double   g_tp           = 0;
double   g_riskAmount   = 0;
double   g_mfeR         = 0;     // max favorable excursion (R)
double   g_maeR         = 0;     // max adverse excursion (R, positive)
double   g_minProfitR   = 0;     // running minimum signed R
datetime g_entryTime    = 0;
int      g_entryWeekday = 0;
int      g_entryGmtHour = 0;
int      g_entrySession = 0;

//+------------------------------------------------------------------+
//| SYMBOL AUTO-DETECTION                                             |
//+------------------------------------------------------------------+
string DetectSymbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("OBREC: Override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string candidates[] = {
      "GER40", "GER40.s", "GER40.cash", "GER40+", "GER40ft",
      "DE40", "DE40+", "DAX40", "DAX", "Germany40", "DEU40",
      "DEU40.cash", "GER40m", "GER40fs", "DAX.fs", "DE40fs"
   };
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolSelect(candidates[i], true))
      {
         double bid = SymbolInfoDouble(candidates[i], SYMBOL_BID);
         if(bid > 0)
         {
            Print("OBREC: Detected symbol: ", candidates[i], " bid=", bid);
            return candidates[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("OBREC: WARNING - No DE40 symbol found, using chart symbol: ", _Symbol);
   return _Symbol;
}

//+------------------------------------------------------------------+
//| INIT                                                              |
//+------------------------------------------------------------------+
int OnInit()
{
   // clamp ranged inputs into working state
   g_impulseMult   = MathMax(1.0, MathMin(2.0, InpImpulseMult));
   g_maxObAge      = MathMax(10,  MathMin(60,  InpMaxOBage));
   g_confirmCloses = MathMax(1,   MathMin(5,   InpConfirmCloses));
   g_tpRR          = MathMax(0.8, MathMin(1.5, InpTP_RR));

   g_symbol = DetectSymbol();
   if(!SymbolSelect(g_symbol, true))
   {
      Print("OBREC: FATAL - cannot select symbol: ", g_symbol);
      return INIT_FAILED;
   }
   g_digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);

   g_hATR = iATR(g_symbol, PERIOD_M15, ATR_PERIOD);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("OBREC: FATAL - ATR14 handle failed");
      return INIT_FAILED;
   }
   if(InpTrendGate)
   {
      g_hEMA = iMA(g_symbol, PERIOD_M15, TREND_EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hEMA == INVALID_HANDLE)
      {
         Print("OBREC: FATAL - EMA200 handle failed");
         return INIT_FAILED;
      }
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_logFile = StringFormat("DE40X1_TRADES_%d.csv", InpMagic);

   Print("=== DE40 OBREC — Order-Block Reclamation Harness ===");
   Print("Symbol: ", g_symbol, " | digits: ", g_digits);
   Print("Magic: ", InpMagic, " | log: ", g_logFile);
   Print("ImpulseMult: ", DoubleToString(g_impulseMult, 2), " x ATR14 (M15)");
   Print("MaxOBage: ", g_maxObAge, " bars | ConfirmCloses: ", g_confirmCloses);
   Print("TP RR: ", DoubleToString(g_tpRR, 2), " | Risk: ", DoubleToString(InpRiskPct, 2), "%");
   Print("TrendGate(EMA200): ", InpTrendGate ? "ON" : "OFF");
   Print("MaxSpread: ", InpMaxSpreadPts, " pts");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_hATR != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hEMA != INVALID_HANDLE) IndicatorRelease(g_hEMA);
}

//+------------------------------------------------------------------+
//| ATR14 (M15), completed bar value                                  |
//+------------------------------------------------------------------+
double GetATR()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hATR, 0, 0, 3, buf) < 3) return 0;
   return buf[1];
}

//+------------------------------------------------------------------+
//| EMA200 slope: +1 rising, -1 falling, 0 neutral/insufficient        |
//+------------------------------------------------------------------+
int EMA200Slope()
{
   if(g_hEMA == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   int need = TREND_SLOPE_LB + 1;
   if(CopyBuffer(g_hEMA, 0, 0, need, buf) < need) return 0;
   double cur  = buf[0];
   double prev = buf[TREND_SLOPE_LB];
   if(cur > prev) return 1;
   if(cur < prev) return -1;
   return 0;
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

// Session bucket (GMT). Mirrors DE40 X1 session semantics:
//   1 = Frankfurt 07-08, 2 = London 08-11 (incl Xetra cash), 4 = US overlap 13:30-16, 0 = OOH
int SessionBucket(int gmtMinOfDay)
{
   if(gmtMinOfDay >= 7 * 60 && gmtMinOfDay < 8 * 60)  return 1;
   if(gmtMinOfDay >= 8 * 60 && gmtMinOfDay < 11 * 60) return 2;
   if(gmtMinOfDay >= 13 * 60 + 30 && gmtMinOfDay < 16 * 60) return 4;
   return 0;
}

//+------------------------------------------------------------------+
//| Find the latest valid impulse candle and its order block.          |
//| Scans completed M15 bars from newest (shift 1) back to MaxOBage.  |
//+------------------------------------------------------------------+
bool FindLatestImpulse(double atr, int &impShift, int &obShift,
                       double &zoneHigh, double &zoneLow, int &dir)
{
   for(int i = 1; i <= g_maxObAge; i++)
   {
      double o = iOpen(g_symbol, PERIOD_M15, i);
      double c = iClose(g_symbol, PERIOD_M15, i);
      double body = MathAbs(c - o);
      if(body < g_impulseMult * atr) continue;

      int d = (c > o) ? 1 : -1;   // impulse direction

      // last opposite-direction candle before the impulse
      int j = -1;
      for(int k = i + 1; k <= g_maxObAge; k++)
      {
         double ko = iOpen(g_symbol, PERIOD_M15, k);
         double kc = iClose(g_symbol, PERIOD_M15, k);
         if(d == 1 && kc < ko)  { j = k; break; }   // bullish impulse -> bearish OB
         if(d == -1 && kc > ko) { j = k; break; }   // bearish impulse -> bullish OB
      }
      if(j < 0) continue;            // no opposite candle inside age window
      if(iTime(g_symbol, PERIOD_M15, j) <= g_lastObTime) continue; // already consumed

      double obO = iOpen(g_symbol, PERIOD_M15, j);
      double obC = iClose(g_symbol, PERIOD_M15, j);
      zoneHigh = MathMax(obO, obC);
      zoneLow  = MathMin(obO, obC);
      impShift = i;
      obShift  = j;
      dir      = d;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Arm a fresh order-block reclamation setup                          |
//+------------------------------------------------------------------+
void ArmNewSetup(double atr)
{
   int impShift, obShift, dir;
   double zoneHigh, zoneLow;
   if(!FindLatestImpulse(atr, impShift, obShift, zoneHigh, zoneLow, dir))
      return;
   if(dir == 1 && !InpAllowLong)   return;
   if(dir == -1 && !InpAllowShort) return;

   g_armed        = true;
   g_obDir        = dir;
   g_obZoneHigh   = zoneHigh;
   g_obZoneLow    = zoneLow;
   g_obBarTime    = iTime(g_symbol, PERIOD_M15, obShift);
   g_obAgeBars    = obShift;      // bars ago at arm time
   g_mitigated    = false;
   g_confirmCount = 0;

   Print("OBREC_ARMED | ", (dir == 1) ? "BUY" : "SELL",
         " | zone[", DoubleToString(zoneLow, g_digits), " .. ",
         DoubleToString(zoneHigh, g_digits), "] | obAge=", obShift);
}

//+------------------------------------------------------------------+
//| Evaluate armed setup on each new completed M15 bar                 |
//+------------------------------------------------------------------+
void EvaluateArmed(double atr)
{
   g_obAgeBars++;
   if(g_obAgeBars > g_maxObAge)
   {
      Print("OBREC_AGE_EXPIRED | obAge=", g_obAgeBars);
      ResetArmed();
      return;
   }

   int shift = 1;   // the just-completed bar
   double h = iHigh(g_symbol, PERIOD_M15, shift);
   double l = iLow(g_symbol, PERIOD_M15, shift);
   double c = iClose(g_symbol, PERIOD_M15, shift);

   // mitigation: price sweeps "through" the whole zone
   if(!g_mitigated)
   {
      if(g_obDir == 1)
      {
         if(l <= g_obZoneLow) g_mitigated = true;
      }
      else
      {
         if(h >= g_obZoneHigh) g_mitigated = true;
      }
   }
   if(!g_mitigated) return;

   // confirmation: consecutive closes back beyond the far edge
   bool beyond = (g_obDir == 1) ? (c > g_obZoneHigh) : (c < g_obZoneLow);
   if(beyond) g_confirmCount++;
   else       g_confirmCount = 0;

   if(g_confirmCount < g_confirmCloses) return;

   AttemptEntry(atr);
}

//+------------------------------------------------------------------+
//| Entry placement (direction = impulse direction)                    |
//+------------------------------------------------------------------+
void AttemptEntry(double atr)
{
   long spread = SymbolInfoInteger(g_symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts)
   {
      Print("OBREC_SPREAD_REJECT | spread=", spread, " > ", InpMaxSpreadPts);
      return;
   }

   if(InpTrendGate)
   {
      int slope = EMA200Slope();
      if(slope == 0) return;                                // neutral/insufficient
      if(g_obDir == 1 && slope < 0) return;                 // long needs rising EMA
      if(g_obDir == -1 && slope > 0) return;                // short needs falling EMA
   }

   double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double entry = (g_obDir == 1) ? ask : bid;

   double sl, tp, risk;
   if(g_obDir == 1)
   {
      sl   = g_obZoneLow - SL_BUFFER_ATR * atr;   // beyond zone + buffer
      risk = entry - sl;
      tp   = entry + risk * g_tpRR;
   }
   else
   {
      sl   = g_obZoneHigh + SL_BUFFER_ATR * atr;
      risk = sl - entry;
      tp   = entry - risk * g_tpRR;
   }
   if(risk <= 0) return;
   if(g_obDir == 1 && sl >= entry) return;
   if(g_obDir == -1 && sl <= entry) return;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   sl = NormalizeDouble(sl, g_digits);
   tp = NormalizeDouble(tp, g_digits);
   string comment = "OBREC_" + ((g_obDir == 1) ? "L" : "S");

   bool ok = (g_obDir == 1) ? trade.Buy(lots, g_symbol, entry, sl, tp, comment)
                            : trade.Sell(lots, g_symbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("OBREC_ENTRY_REJECTED | ", comment, " | ", GetLastError());
      return;
   }

   double fill = trade.ResultPrice();
   g_inPosition = true;
   g_tradeDir   = g_obDir;
   g_entryPrice = (fill > 0) ? fill : entry;
   g_sl         = sl;
   g_tp         = tp;
   g_riskAmount = MathAbs(g_entryPrice - sl);
   g_mfeR       = 0;
   g_maeR       = 0;
   g_minProfitR = 0;
   g_entryTime  = TimeCurrent();

   int wd, gh, gmo;
   ComputeGmt(g_entryTime, wd, gh, gmo);
   g_entryWeekday = wd;
   g_entryGmtHour = gh;
   g_entrySession = SessionBucket(gmo);

   g_lastObTime = g_obBarTime;   // consume this OB
   ResetArmed();

   Print("OBREC_ENTRY | ", comment, " | entry=", DoubleToString(g_entryPrice, g_digits),
         " | sl=", DoubleToString(g_sl, g_digits),
         " | tp=", DoubleToString(g_tp, g_digits),
         " | lots=", DoubleToString(lots, 2));
}

//+------------------------------------------------------------------+
//| Lot sizing from fixed risk %                                      |
//+------------------------------------------------------------------+
double CalcLots(double risk)
{
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;
   double tickVal  = SymbolInfoDouble(g_symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(g_symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || risk <= 0) return 0;
   double lots = riskMoney / (risk / tickSize * tickVal);
   double minLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);
   if(lotStep > 0) lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);
   return lots;
}

//+------------------------------------------------------------------+
//| Live position tracking: MFE/MAE per tick + close detection        |
//+------------------------------------------------------------------+
void ManageOpenPosition()
{
   int total = PositionsTotal();
   bool found = false;
   for(int i = total - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      found = true;
      break;
   }
   if(!found)
   {
      LogClosedTrade();
      ResetPositionState();
      return;
   }

   if(g_riskAmount <= 0 || g_tradeDir == 0) return;
   double cur = (g_tradeDir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_BID)
                                  : SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double profitR = (g_tradeDir == 1) ? (cur - g_entryPrice) / g_riskAmount
                                      : (g_entryPrice - cur) / g_riskAmount;
   if(profitR > g_mfeR)        g_mfeR = profitR;
   if(profitR < g_minProfitR)  g_minProfitR = profitR;
}

//+------------------------------------------------------------------+
//| Resolve exit price from deal history and write the trade CSV row  |
//+------------------------------------------------------------------+
void LogClosedTrade()
{
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
      int de = (int)HistoryDealGetInteger(dk, DEAL_ENTRY);
      if(de == DEAL_ENTRY_OUT || de == DEAL_ENTRY_INOUT)
      {
         exitPrice = HistoryDealGetDouble(dk, DEAL_PRICE);
         closeTime = (datetime)HistoryDealGetInteger(dk, DEAL_TIME);
         break;
      }
   }
   if(exitPrice <= 0)
   {
      Print("OBREC_CLOSE | no exit deal found, skipping CSV");
      return;
   }

   double R = (g_riskAmount > 0)
              ? ((g_tradeDir == 1) ? (exitPrice - g_entryPrice) / g_riskAmount
                                   : (g_entryPrice - exitPrice) / g_riskAmount)
              : 0;
   g_maeR = (g_minProfitR < 0) ? -g_minProfitR : 0;
   WriteTradeLog(closeTime, exitPrice, R);

   Print("OBREC_CLOSE | ", (g_tradeDir == 1) ? "BUY" : "SELL",
         " | exit=", DoubleToString(exitPrice, g_digits),
         " | R=", DoubleToString(R, 3),
         " | MFE=", DoubleToString(g_mfeR, 3),
         " | MAE=", DoubleToString(g_maeR, 3));
}

//+------------------------------------------------------------------+
//| Append one trade row to the per-magic CSV (terminal Files dir)    |
//+------------------------------------------------------------------+
void WriteTradeLog(datetime closeTime, double exitPrice, double R)
{
   int handle = INVALID_HANDLE;
   bool exists = FileIsExist(g_logFile, FILE_COMMON);
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
             "OBREC",
             IntegerToString(g_entryWeekday),
             IntegerToString(g_entryGmtHour),
             IntegerToString(g_entrySession),
             "OBREC_" + ((g_tradeDir == 1) ? "L" : "S"));
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| RESET HELPERS                                                     |
//+------------------------------------------------------------------+
void ResetArmed()
{
   g_armed        = false;
   g_obDir        = 0;
   g_obZoneHigh   = 0;
   g_obZoneLow    = 0;
   g_obBarTime    = 0;
   g_obAgeBars    = 0;
   g_mitigated    = false;
   g_confirmCount = 0;
}

void ResetPositionState()
{
   g_inPosition   = false;
   g_tradeDir     = 0;
   g_entryPrice   = 0;
   g_sl           = 0;
   g_tp           = 0;
   g_riskAmount   = 0;
   g_mfeR         = 0;
   g_maeR         = 0;
   g_minProfitR   = 0;
   g_entryTime    = 0;
   g_entryWeekday = 0;
   g_entryGmtHour = 0;
   g_entrySession = 0;
}

//+------------------------------------------------------------------+
//| ON TICK                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Live tracking + close detection (every tick) while in position
   if(g_inPosition)
   {
      ManageOpenPosition();
      return;   // one position: block new entries
   }

   // 2. New M15 bar boundary?
   datetime barTime = iTime(g_symbol, PERIOD_M15, 0);
   if(barTime == 0 || barTime == g_lastBarTime) return;
   g_lastBarTime = barTime;

   // 3. ATR gate
   double atr = GetATR();
   if(atr <= 0) return;

   // 4. Armed setup evaluation, or a fresh scan
   if(g_armed) EvaluateArmed(atr);
   else        ArmNewSetup(atr);
}
//+------------------------------------------------------------------+
