//+------------------------------------------------------------------+
//| DE40_EXHREJ_HARNESS.mq5                                           |
//| Standalone research harness — EXHREJ (Exhaustion/Rejection fade)  |
//| Magic base: 4200                                                   |
//| CSV: DE40X1_TRADES_4200.csv (terminal Files dir)                  |
//+------------------------------------------------------------------+
//| Strategy (fade family):                                            |
//|   Levels  = PDH / PDL from D1 (shift 1).                          |
//|   Exhaustion event = price extends beyond a level by               |
//|     InpExtendATR * ATR14(M15), then prints a rejection candle.     |
//|   Rejection candle = wick ratio >= InpWickRatio of candle range    |
//|     AND tick-volume >= InpVolSpikeMult x 20-bar mean.              |
//|   Entry  = close back inside the level (reclaim).                  |
//|   Direction = fade the extension (both sides).                     |
//|   SL     = beyond the extension extreme + InpSLBufferATR * ATR.    |
//|   TP     = InpTPMode: fixed R | session VWAP | opposite PD level.  |
//|   Session VWAP = typical-price/tick-volume anchored at 07:00 GMT   |
//|     (server hour derived via InpServerUTC).                        |
//|   One position; spread guard; per-trade CSV + MFE/MAE.            |
//+------------------------------------------------------------------+
//| Signal engine runs on PERIOD_M15 regardless of chart timeframe.   |
//| CS    V columns: time_open,time_close,side,entry,sl,tp,exit_price,|
//|       R,MFE_R,MAE_R,module,weekday,gmt_hour,session_bucket,comment|
//| weekday: MQL5 day_of_week (0=Sun .. 6=Sat).                       |
//| session_bucket (GMT): 0=00-06 Asia/pre, 1=07 Frankfurt open,      |
//|   2=08-10 London/Xetra morning, 3=11-12:29 London mid,            |
//|   4=12:30-13:59 news window, 5=14-15 US overlap, 6=16-23 late.    |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 EXHREJ — Exhaustion/Rejection fade at PDH/PDL extremes (harness)"

#include <Trade\Trade.mqh>
CTrade trade;

//+------------------------------------------------------------------+
//| ENUMS                                                            |
//+------------------------------------------------------------------+
enum ENUM_EXHREJ_TP
{
   TP_FIXED_RR = 0,  // Fixed R (InpTP_RR)
   TP_VWAP     = 1,  // Mean reversion to session VWAP
   TP_OPP_PD   = 2   // Opposite PD level
};

//+------------------------------------------------------------------+
//| INPUTS                                                           |
//+------------------------------------------------------------------+
input group "=== Symbol Configuration ==="
input string InpSymbolOverride = "";   // Override symbol (empty = auto-detect)
input int    InpServerUTC      = 2;    // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== Exhaustion Geometry ==="
input double InpExtendATR     = 0.7;   // exhaustion extension beyond level (ATR)
input double InpWickRatio     = 0.6;   // rejection candle wick ratio of range
input double InpVolSpikeMult  = 2.0;   // tick-volume spike vs 20-bar mean
input int    InpATRPeriod     = 14;    // ATR period (M15)
input double InpSLBufferATR   = 0.3;   // SL buffer beyond extreme (ATR)
input int    InpMaxExtBars    = 6;     // max M15 bars waiting for rejection
input double InpMaxRiskATR    = 5.0;   // max stop distance (ATR)

input group "=== Take Profit ==="
input ENUM_EXHREJ_TP InpTPMode = TP_FIXED_RR; // TP mode
input double InpTP_RR          = 1.0;   // fixed R (TP_FIXED_RR mode)
input double InpMinTP_R        = 0.5;   // min TP distance vs risk

input group "=== Session VWAP (TP_VWAP mode) ==="
input int    InpVwapAnchorGMT  = 7;     // session VWAP anchor hour (GMT)

input group "=== Sessions ==="
input bool   InpAllowLong      = true;  // allow long fade entries
input bool   InpAllowShort     = true;  // allow short fade entries
input int    InpSessionStartGMT= 0;     // entry window start (GMT hour)
input int    InpSessionEndGMT  = 24;    // entry window end (GMT hour, 24=all day)
input bool   InpNewsBlock      = true;  // block entries during news window
input int    InpNewsStartGMT   = 12;    // news window start hour (GMT)
input int    InpNewsStartMin   = 30;    // news window start minute
input int    InpNewsEndGMT     = 14;    // news window end hour (GMT)
input int    InpNewsEndMin     = 0;     // news window end minute

input group "=== Trade Management ==="
input long   InpMagic          = 4200;  // magic number (EXHREJ base)
input double InpRiskPct        = 1.0;   // risk per trade (% of balance)
input double InpFixedLots      = 0.0;   // >0 overrides risk pct
input int    InpMaxSpreadPts   = 500;   // spread guard (points)

input group "=== Volatility & Safety ==="
input double InpMinATR         = 5.0;   // min ATR floor (index points)
input double InpMaxATR         = 800.0; // max ATR ceiling (index points)
input int    InpMaxTradesDay   = 0;     // max trades per day (0=unlimited)
input int    InpStopLossDay    = 0;     // daily loss limit (0=off)
input int    InpColdStartSec   = 30;    // cold-start window (seconds)

//+------------------------------------------------------------------+
//| GLOBALS                                                          |
//+------------------------------------------------------------------+
string   g_activeSymbol = "";
int      g_hATR = INVALID_HANDLE;

datetime g_lastBar    = 0;   // last processed M15 bar
datetime g_today      = 0;   // server-date of current trading day
datetime g_attachTime = 0;

int      g_tradesToday = 0;
int      g_lossesToday = 0;

// extension state (awaiting a rejection candle)
bool     g_shortExt     = false;  // extension above PDH awaiting short fade
double   g_shortExtreme = 0;      // highest high of extension
int      g_shortExtBars = 0;      // bars since extension first seen
bool     g_longExt      = false;  // extension below PDL awaiting long fade
double   g_longExtreme  = 0;      // lowest low of extension
int      g_longExtBars  = 0;      // bars since extension first seen

// active position state
bool     g_inPosition   = false;
int      g_tradeDir     = 0;
double   g_entryPrice   = 0;
double   g_riskAmount   = 0;      // initial risk (price distance)
double   g_entrySl      = 0;
double   g_entryTp      = 0;
datetime g_entryTime    = 0;
double   g_mfeR         = 0;      // max favorable excursion (positive magnitude)
double   g_maeR         = 0;      // max adverse excursion (positive magnitude)
int      g_entryWeekday = 0;
int      g_entryGmtHour = 0;
int      g_entryBucket  = 0;
string   g_entryComment = "";
ulong    g_posTicket    = 0;

//+------------------------------------------------------------------+
//| SYMBOL AUTO-DETECTION                                            |
//+------------------------------------------------------------------+
string DetectDE40Symbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("EXHREJ: Override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string candidates[] = {
      "GER40", "GER40.cash", "GER40+", "DE40", "DE40+",
      "DAX40", "DAX", "Germany40", "DEU40", "DEU40.cash",
      "GER40m", "GER40fs", "DAX.fs", "DE40fs", "GER40.s"
   };
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolSelect(candidates[i], true))
      {
         double bid = SymbolInfoDouble(candidates[i], SYMBOL_BID);
         if(bid > 0)
         {
            Print("EXHREJ: Detected symbol: ", candidates[i], " bid=", bid);
            return candidates[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("EXHREJ: WARNING - No DE40 symbol found, using chart symbol: ", _Symbol);
   return _Symbol;
}

void LogSymbolSpecs()
{
   Print("=== EXHREJ Symbol Specifications ===");
   Print("Symbol: ", g_activeSymbol);
   Print("Digits: ", (int)SymbolInfoInteger(g_activeSymbol, SYMBOL_DIGITS));
   Print("Point: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_POINT));
   Print("Spread: ", SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD), " pts");
   Print("Min Lot: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN));
   Print("Lot Step: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP));
}

//+------------------------------------------------------------------+
//| INIT / DEINIT                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_activeSymbol = DetectDE40Symbol();
   if(!SymbolSelect(g_activeSymbol, true))
   {
      Print("EXHREJ: FATAL - Cannot select symbol: ", g_activeSymbol);
      return INIT_FAILED;
   }

   g_hATR = iATR(g_activeSymbol, PERIOD_M15, InpATRPeriod);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("EXHREJ: FATAL - ATR handle failed");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_lastBar     = 0;
   g_today       = 0;
   g_attachTime  = TimeCurrent();
   g_tradesToday = 0;
   g_lossesToday = 0;
   ResetSetupState();
   ResetPosState();

   Print("=== DE40 EXHREJ v1.00 — Exhaustion/Rejection Fade Harness ===");
   Print("Symbol: ", g_activeSymbol);
   Print("Magic: ", InpMagic, " | CSV: DE40X1_TRADES_", InpMagic, ".csv");
   Print("ExtendATR=", DoubleToString(InpExtendATR, 2),
         " WickRatio=", DoubleToString(InpWickRatio, 2),
         " VolSpike=", DoubleToString(InpVolSpikeMult, 2));
   Print("SLBufferATR=", DoubleToString(InpSLBufferATR, 2),
         " | TP mode=", (int)InpTPMode, " | TP_RR=", DoubleToString(InpTP_RR, 2));
   Print("Session: ", InpSessionStartGMT, ":00-",
         (InpSessionEndGMT >= 24 ? "24:00" : IntegerToString(InpSessionEndGMT) + ":00"),
         " GMT | News block: ", InpNewsBlock ? "12:30-14:00 GMT" : "OFF");
   Print("VWAP anchor: ", InpVwapAnchorGMT, ":00 GMT | ServerUTC=", InpServerUTC);
   LogSymbolSpecs();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hATR != INVALID_HANDLE) IndicatorRelease(g_hATR);
}

//+------------------------------------------------------------------+
//| STATE RESET HELPERS                                             |
//+------------------------------------------------------------------+
void ResetSetupState()
{
   g_shortExt     = false;
   g_shortExtreme = 0;
   g_shortExtBars = 0;
   g_longExt      = false;
   g_longExtreme  = 0;
   g_longExtBars  = 0;
}

void ResetPosState()
{
   g_inPosition   = false;
   g_tradeDir     = 0;
   g_entryPrice   = 0;
   g_riskAmount   = 0;
   g_entrySl      = 0;
   g_entryTp      = 0;
   g_entryTime    = 0;
   g_mfeR         = 0;
   g_maeR         = 0;
   g_entryWeekday = 0;
   g_entryGmtHour = 0;
   g_entryBucket  = 0;
   g_entryComment = "";
   g_posTicket    = 0;
}

//+------------------------------------------------------------------+
//| TIME HELPERS (all session logic in GMT via InpServerUTC)         |
//+------------------------------------------------------------------+
int GmtHourOf(const MqlDateTime &dt)
{
   int h = dt.hour - InpServerUTC;
   if(h < 0)      h += 24;
   if(h >= 24)    h -= 24;
   return h;
}

int GmtMinOfDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour - InpServerUTC;
   if(h < 0)   h += 24;
   if(h >= 24) h -= 24;
   return h * 60 + dt.min;
}

//+------------------------------------------------------------------+
//| Session bucket (GMT). See header comment for legend.             |
//+------------------------------------------------------------------+
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
bool InSessionWindow(int gmtMin)
{
   int start = InpSessionStartGMT * 60;
   int end   = InpSessionEndGMT * 60;
   if(end <= start) return false;
   return (gmtMin >= start && gmtMin < end);
}

bool InNewsWindow(int gmtMin)
{
   if(!InpNewsBlock) return false;
   int s = InpNewsStartGMT * 60 + InpNewsStartMin;
   int e = InpNewsEndGMT   * 60 + InpNewsEndMin;
   if(e <= s) return false;
   return (gmtMin >= s && gmtMin < e);
}

//+------------------------------------------------------------------+
//| INDICATOR / DATA HELPERS                                        |
//+------------------------------------------------------------------+
double GetATR()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hATR, 0, 1, 2, buf) < 2) return 0;
   return buf[0];
}

//+------------------------------------------------------------------+
//| Session VWAP: sum(typical_price * tick_volume)/sum(vol) from the  |
//| 07:00 GMT anchor over completed M1 bars (excludes forming bar).   |
//+------------------------------------------------------------------+
bool SessionVwap(double &vwap)
{
   vwap = 0;
   if(g_today == 0) return false;
   int anchorSrvHour = (InpVwapAnchorGMT + InpServerUTC) % 24;
   datetime tStart = g_today + (datetime)(anchorSrvHour * 3600);
   if(TimeCurrent() < tStart + 300) return false;
   int sStart = iBarShift(g_activeSymbol, PERIOD_M1, tStart, false);
   if(sStart < 3) return false;

   double sumPV = 0, sumV = 0;
   for(int sh = 2; sh <= sStart; sh++)
   {
      double h = iHigh(g_activeSymbol, PERIOD_M1, sh);
      double l = iLow(g_activeSymbol, PERIOD_M1, sh);
      double c = iClose(g_activeSymbol, PERIOD_M1, sh);
      if(h <= 0 || l <= 0) continue;
      double vol = (double)iVolume(g_activeSymbol, PERIOD_M1, sh);
      if(vol <= 0) vol = 1;
      sumPV += ((h + l + c) / 3.0) * vol;
      sumV  += vol;
   }
   if(sumV <= 0) return false;
   vwap = sumPV / sumV;
   return true;
}

//+------------------------------------------------------------------+
//| REJECTION CANDLE PRIMITIVES (on M15 bar shift 1)                |
//+------------------------------------------------------------------+
double UpperWickRatio(double o, double h, double l, double c)
{
   double range = h - l;
   if(range <= 0) return 0;
   double bodyTop = MathMax(o, c);
   return (h - bodyTop) / range;
}

double LowerWickRatio(double o, double h, double l, double c)
{
   double range = h - l;
   if(range <= 0) return 0;
   double bodyBot = MathMin(o, c);
   return (bodyBot - l) / range;
}

bool VolumeSpike(long vol1)
{
   double avg = 0;
   for(int i = 2; i <= 21; i++)
      avg += (double)iVolume(g_activeSymbol, PERIOD_M15, i);
   avg /= 20.0;
   if(avg <= 0) return false;
   return ((double)vol1 >= InpVolSpikeMult * avg);
}

//+------------------------------------------------------------------+
//| RISK / LOTS                                                     |
//+------------------------------------------------------------------+
double CalcLots(double risk)
{
   double minLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP);
   if(lotStep <= 0 || minLot <= 0) return 0;

   double lots = 0;
   if(InpFixedLots > 0)
   {
      lots = InpFixedLots;
   }
   else
   {
      double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
      double riskMoney = balance * InpRiskPct / 100.0;
      double tickVal  = SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize = SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickVal <= 0 || tickSize <= 0 || risk <= 0) return 0;
      lots = riskMoney / (risk / tickSize * tickVal);
   }

   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);
   return lots;
}

//+------------------------------------------------------------------+
//| ENTRY PLACEMENT                                                 |
//+------------------------------------------------------------------+
void ExecuteEntry(int dir, double sl, double pdh, double pdl, double atr, string comment)
{
   if(dir == 1  && !InpAllowLong)  return;
   if(dir == -1 && !InpAllowShort) return;

   long spreadPts = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPts)
   {
      Print("EXHREJ: entry skipped — spread ", spreadPts, " > ", InpMaxSpreadPts);
      return;
   }

   double entry = (dir == 1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK)
                             : SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
   double risk = MathAbs(entry - sl);
   if(risk <= 0 || risk > InpMaxRiskATR * atr) return;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   // --- target selection ---
   double tp = 0;
   switch(InpTPMode)
   {
      case TP_FIXED_RR:
         tp = (dir == 1) ? entry + risk * InpTP_RR : entry - risk * InpTP_RR;
         break;
      case TP_VWAP:
      {
         double vwap = 0;
         if(SessionVwap(vwap)) tp = vwap;
         break;
      }
      case TP_OPP_PD:
         tp = (dir == 1) ? pdh : pdl;
         break;
   }

   bool tpValid = (tp > 0) &&
                  ((dir == 1 && tp > entry) || (dir == -1 && tp < entry)) &&
                  (MathAbs(tp - entry) >= InpMinTP_R * risk);
   if(!tpValid)
      tp = (dir == 1) ? entry + risk * InpTP_RR : entry - risk * InpTP_RR;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   trade.SetExpertMagicNumber(InpMagic);
   bool ok = (dir == 1) ? trade.Buy(lots, g_activeSymbol, entry, sl, tp, comment)
                        : trade.Sell(lots, g_activeSymbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("EXHREJ: order rejected | ", comment);
      return;
   }
   g_inPosition   = true;
   g_tradesToday++;
   double fill = trade.ResultPrice();
   g_entryPrice = (fill > 0) ? fill : entry;
   g_riskAmount = risk;
   g_tradeDir   = dir;
   g_entrySl    = sl;
   g_entryTp    = tp;
   g_entryTime  = TimeCurrent();
   g_mfeR       = 0;
   g_maeR       = 0;
   g_entryComment = comment;
   g_posTicket    = trade.ResultOrder();

   MqlDateTime dtE;
   TimeToStruct(g_entryTime, dtE);
   g_entryWeekday = dtE.day_of_week;
   int gmh = GmtHourOf(dtE);
   g_entryGmtHour = gmh;
   g_entryBucket  = SessionBucket(GmtMinOfDay());

   Print("EXHREJ: TRADE_OPENED | ", comment, " | ", (dir==1)?"BUY":"SELL",
         " | lots=", DoubleToString(lots, 2),
         " | entry=", DoubleToString(g_entryPrice, _Digits),
         " | sl=", DoubleToString(sl, _Digits),
         " | tp=", DoubleToString(tp, _Digits),
         " | risk=", DoubleToString(risk, _Digits),
         " | R=", DoubleToString(risk / atr, 2), "ATR",
         " | gmt=", IntegerToString(gmh), "h");
}

//+------------------------------------------------------------------+
//| SIGNAL EVALUATION (once per new M15 bar)                        |
//+------------------------------------------------------------------+
void EvaluateSetup()
{
   if(g_inPosition) return;
   if(tradesTodayLimit()) return;

   double atr = GetATR();
   if(atr <= 0 || atr < InpMinATR || atr > InpMaxATR) return;

   double pdh = iHigh(g_activeSymbol, PERIOD_D1, 1);
   double pdl = iLow(g_activeSymbol, PERIOD_D1, 1);
   if(pdh <= 0 || pdl <= 0 || pdh <= pdl) return;

   if(Bars(g_activeSymbol, PERIOD_M15) < 40) return;

   double o1 = iOpen(g_activeSymbol, PERIOD_M15, 1);
   double h1 = iHigh(g_activeSymbol, PERIOD_M15, 1);
   double l1 = iLow(g_activeSymbol, PERIOD_M15, 1);
   double c1 = iClose(g_activeSymbol, PERIOD_M15, 1);
   long   v1 = iVolume(g_activeSymbol, PERIOD_M15, 1);
   if(h1 <= 0 || l1 <= 0) return;

   // ---- SHORT fade: extension above PDH ---- //
   if(!g_shortExt)
   {
      if(h1 >= pdh + InpExtendATR * atr)
      {
         g_shortExt = true;
         g_shortExtreme = h1;
         g_shortExtBars = 0;
      }
   }
   else
   {
      g_shortExtBars++;
      if(h1 > g_shortExtreme) g_shortExtreme = h1;
      if(g_shortExtBars > InpMaxExtBars) g_shortExt = false;
   }

   if(g_shortExt &&
      UpperWickRatio(o1, h1, l1, c1) >= InpWickRatio &&
      VolumeSpike(v1) &&
      c1 < pdh)
   {
      double sl = g_shortExtreme + InpSLBufferATR * atr;
      g_shortExt = false;
      ExecuteEntry(-1, sl, pdh, pdl, atr, "EXHREJ_S");
      if(g_inPosition) { ResetSetupState(); return; }
   }

   // ---- LONG fade: extension below PDL ---- //
   if(!g_longExt)
   {
      if(l1 <= pdl - InpExtendATR * atr)
      {
         g_longExt = true;
         g_longExtreme = l1;
         g_longExtBars = 0;
      }
   }
   else
   {
      g_longExtBars++;
      if(l1 < g_longExtreme) g_longExtreme = l1;
      if(g_longExtBars > InpMaxExtBars) g_longExt = false;
   }

   if(g_longExt &&
      LowerWickRatio(o1, h1, l1, c1) >= InpWickRatio &&
      VolumeSpike(v1) &&
      c1 > pdl)
   {
      double sl = g_longExtreme - InpSLBufferATR * atr;
      g_longExt = false;
      ExecuteEntry(1, sl, pdh, pdl, atr, "EXHREJ_L");
      if(g_inPosition) ResetSetupState();
   }
}

bool tradesTodayLimit()
{
   if(InpMaxTradesDay <= 0) return false;
   return (g_tradesToday >= InpMaxTradesDay);
}

//+------------------------------------------------------------------+
//| POSITION MANAGEMENT (per tick: MFE/MAE + close detection)       |
//+------------------------------------------------------------------+
void ManagePosition()
{
   if(!g_inPosition) return;

   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_activeSymbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
      {
         found = true;
         break;
      }
   }

   if(!found)
   {
      TrackAndLogClose();
      ResetPosState();
      return;
   }

   // per-tick MFE/MAE tracking
   double cur = (g_tradeDir == 1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_BID)
                                  : SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
   if(g_riskAmount > 0 && cur > 0)
   {
      double pR = (g_tradeDir == 1) ? (cur - g_entryPrice) / g_riskAmount
                                    : (g_entryPrice - cur) / g_riskAmount;
      if(pR > g_mfeR) g_mfeR = pR;
      double adverse = -pR;
      if(adverse > g_maeR) g_maeR = adverse;
   }
}

//+------------------------------------------------------------------+
//| CLOSE DETECTION + CSV LOGGING                                   |
//+------------------------------------------------------------------+
void TrackAndLogClose()
{
   if(g_tradeDir == 0 || g_entryPrice == 0 || g_riskAmount <= 0) return;

   double exitPrice = 0;
   HistorySelect(g_entryTime - 86400, TimeCurrent() + 60);
   int totalDeals = HistoryDealsTotal();
   for(int i = totalDeals - 1; i >= 0; i--)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(dt == 0) continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != g_activeSymbol) continue;
      if(HistoryDealGetInteger(dt, DEAL_MAGIC) != (long)InpMagic) continue;
      int entry = (int)HistoryDealGetInteger(dt, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
      {
         exitPrice = HistoryDealGetDouble(dt, DEAL_PRICE);
         break;
      }
   }
   if(exitPrice <= 0) return;

   double pnl = (g_tradeDir == 1) ? (exitPrice - g_entryPrice)
                                  : (g_entryPrice - exitPrice);
   double rr = pnl / g_riskAmount;
   if(pnl < 0)
   {
      g_lossesToday++;
      if(InpStopLossDay > 0 && g_lossesToday >= InpStopLossDay)
         Print("EXHREJ: DAILY LOSS LIMIT REACHED");
   }

   WriteTradeCsv(g_entryTime, TimeCurrent(), g_tradeDir,
                 g_entryPrice, g_entrySl, g_entryTp, exitPrice,
                 rr, g_mfeR, g_maeR, "EXHREJ",
                 g_entryWeekday, g_entryGmtHour, g_entryBucket, g_entryComment);

   Print("EXHREJ: TRADE_CLOSED | ", g_entryComment, " | exit=",
         DoubleToString(exitPrice, _Digits), " | R=", DoubleToString(rr, 3),
         " | MFE=", DoubleToString(g_mfeR, 3), "R | MAE=", DoubleToString(g_maeR, 3), "R");
}

void WriteTradeCsv(datetime timeOpen, datetime timeClose, int side,
                   double entry, double sl, double tp, double exitPrice,
                   double r, double mfeR, double maeR, string module,
                   int weekday, int gmtHour, int sessionBucket, string comment)
{
   string fname = StringFormat("DE40X1_TRADES_%d.csv", (int)InpMagic);

   if(!FileIsExist(fname, FILE_COMMON))
   {
      int h = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      if(h == INVALID_HANDLE)
      {
         Print("EXHREJ: CSV create failed: ", fname);
         return;
      }
      FileWrite(h,
         "time_open", "time_close", "side", "entry", "sl", "tp", "exit_price",
         "R", "MFE_R", "MAE_R", "module", "weekday", "gmt_hour",
         "session_bucket", "comment");
      FileClose(h);
   }

  int h2 = FileOpen(fname, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h2 == INVALID_HANDLE)
   {
      Print("EXHREJ: CSV append failed: ", fname);
      return;
   }
   FileSeek(h2, 0, SEEK_END);
   FileWrite(h2,
      TimeToString(timeOpen, TIME_DATE | TIME_SECONDS),
      TimeToString(timeClose, TIME_DATE | TIME_SECONDS),
      (side == 1) ? "BUY" : "SELL",
      DoubleToString(entry, _Digits),
      DoubleToString(sl, _Digits),
      DoubleToString(tp, _Digits),
      DoubleToString(exitPrice, _Digits),
      DoubleToString(r, 4),
      DoubleToString(mfeR, 4),
      DoubleToString(maeR, 4),
      module,
      IntegerToString(weekday),
      IntegerToString(gmtHour),
      IntegerToString(sessionBucket),
      comment);
   FileClose(h2);
}

//+------------------------------------------------------------------+
//| ON TICK                                                         |
//+------------------------------------------------------------------+
void OnTick()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   // day rollover
   datetime newToday = StringToTime(IntegerToString(dt.year) + "." +
                                    IntegerToString(dt.mon)  + "." +
                                    IntegerToString(dt.day));
   if(newToday != g_today)
   {
      g_today       = newToday;
      g_tradesToday = 0;
      g_lossesToday = 0;
      ResetSetupState();
   }

   // weekend skip
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return;

   // process M15 bar boundary for signal eval
   datetime curBar = iTime(g_activeSymbol, PERIOD_M15, 0);
   bool newBar = (curBar > 0 && curBar != g_lastBar);
   if(newBar) g_lastBar = curBar;

   // manage open position every tick
   ManagePosition();
   if(g_inPosition) return;

   if(!newBar) return;

   // entry gates
   if(TimeCurrent() - g_attachTime < InpColdStartSec) return;
   int gmtMin = GmtMinOfDay();
   if(!InSessionWindow(gmtMin)) return;
   if(InNewsWindow(gmtMin)) return;
   if(InpStopLossDay > 0 && g_lossesToday >= InpStopLossDay) return;

   EvaluateSetup();
}
//+------------------------------------------------------------------+
