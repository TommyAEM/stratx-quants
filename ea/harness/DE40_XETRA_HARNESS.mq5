//+------------------------------------------------------------------+
//| DE40_XETRA_HARNESS.mq5                                            |
//| Xetra Cash-Open Continuation (XETRA) — standalone research harness|
//| DE40 (Germany 40 / DAX) on M15. Magic base: 4500.                 |
//| CSV: DE40X1_TRADES_4500.csv (terminal Files dir).                 |
//|                                                                    |
//| Logic (M15, closed bars; entries at new-bar open via market order):|
//|   session = Xetra cash 08:00-10:00 GMT (InpDSTShift for 07-09 DST)|
//|   bias    = first two completed session bars (08:00 & 08:15 GMT)  |
//|             both close>open => long, both close<open => short,    |
//|             else no bias for the day                               |
//|   entry   = after bias, price pulls back to touch EMA20 in bias   |
//|             direction (long: low<=EMA20; short: high>=EMA20),     |
//|             then a completed bar closes in bias direction ->       |
//|             enter at next open                                     |
//|   gate    = EMA200 slope agreement (ablation toggle)               |
//|   SL      = entry -/+ InpSlAtrMult x ATR(14,M15)                   |
//|   TP      = fixed RR                                               |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 XETRA — Xetra cash-open continuation w/ EMA20 pullback + EMA200 trend gate (M15)"

#include <Trade\Trade.mqh>
CTrade trade;

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "=== Symbol & Time ==="
input string InpSymbolOverride = "";   // Override symbol (empty=auto-detect)
input int    InpServerUTC      = 2;    // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== Xetra Session (GMT) ==="
input int    InpXetraStartGMT  = 8;    // Xetra cash open hour GMT (winter 08-10)
input int    InpXetraEndGMT    = 10;   // Xetra cash session end hour GMT
input int    InpDSTShift       = 0;    // DST shift hours (subtract from GMT session; 1=summer 07-09)

input group "=== Bias / Entry (M15) ==="
input int    InpEntryEmaPeriod = 20;   // Pullback EMA period (EMA20)
input int    InpTrendEmaPeriod = 200;  // Trend EMA period (EMA200) for gate
input int    InpTrendSlopeBars = 5;    // EMA200 slope lookback bars (1-20)

input group "=== Trend Gate (ablation) ==="
input bool   InpUseTrendGate   = true; // Ablation: false = no EMA200 trend gate

input group "=== Stops & Targets ==="
input int    InpAtrPeriod      = 14;   // ATR period (M15)
input double InpSlAtrMult      = 1.5;  // SL = entry -/+ this x ATR (1.0-2.5)
input double InpTpRR           = 1.0;  // Fixed take-profit reward:risk (0.8-1.5)

input group "=== Risk & Safety ==="
input bool   InpAllowLong      = true;  // allow long entries
input bool   InpAllowShort     = true;  // allow short entries
input double InpRiskPct        = 1.0;  // Risk per trade (% of balance)
input int    InpMaxSpreadPts   = 500;  // Max spread (points) to allow entry
input int    InpMagic          = 4500; // Expert magic number (XETRA)
input int    InpMaxTradesDay   = 1;    // Daily trade governor

//+------------------------------------------------------------------+
//| Constants & globals                                               |
//+------------------------------------------------------------------+
#define ST_IDLE        0   // bias not resolved (or none for the day)
#define ST_WAIT_TOUCH  1   // bias set, waiting for EMA20 pullback touch
#define ST_WAIT_TRIGGER 2  // touched, waiting for completed bar close in direction

int      g_state    = ST_IDLE;
int      g_bias     = 0;      // +1 long, -1 short, -2 none, 0 unresolved
bool     g_biasDone = false;  // bias decided for the day
bool     g_touched  = false;  // (kept for logging clarity; state machine drives flow)

// Position state (single position, magic 4500)
bool     g_inPosition = false;
datetime g_entryTime  = 0;
double   g_entryPrice = 0;
double   g_sl         = 0;
double   g_tp         = 0;
double   g_riskAmount = 0;
int      g_tradeDir   = 0;
double   g_mfeR       = 0;
double   g_minProfitR = 0;
double   g_maeR       = 0;
int      g_entryWeekday  = 0;
int      g_entryGmtHour  = 0;
int      g_entrySession  = 0;

// Daily / bar context
datetime g_lastBar      = 0;
long     g_gmtDayKey    = 0;
int      g_tradesToday  = 0;

string   g_symbol  = "";
string   g_logFile = "";
int      g_digits  = 0;

int      g_hATR    = INVALID_HANDLE;
int      g_hEMA20  = INVALID_HANDLE;
int      g_hEMA200 = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Symbol auto-detection                                             |
//+------------------------------------------------------------------+
string DetectSymbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("XETRA: override '", InpSymbolOverride, "' not found, auto-detecting");
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
            Print("XETRA: detected symbol ", cand[i]);
            return cand[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("XETRA: WARNING - no DE40 symbol found, using chart symbol ", _Symbol);
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

int EffStartHour() { return InpXetraStartGMT - InpDSTShift; }
int EffEndHour()   { return InpXetraEndGMT  - InpDSTShift; }

// Session bucket (GMT): 1 = Xetra cash session, 0 = OOH
int SessionBucket(int gmtMinOfDay)
{
   int s = EffStartHour();
   int e = EffEndHour();
   if(gmtMinOfDay >= s * 60 && gmtMinOfDay < e * 60)
      return 1;
   return 0;
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

double GetEma20()
{
   if(g_hEMA20 == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hEMA20, 0, 1, 1, buf) < 1) return 0;
   return buf[0];   // shift 1
}

bool TrendGatePass(int dir)
{
   if(!InpUseTrendGate) return true;
   if(g_hEMA200 == INVALID_HANDLE) return false;
   int need = InpTrendSlopeBars + 1;
   double ema[];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(g_hEMA200, 0, 1, need, ema) < need) return false;
   double emaNow  = ema[0];                      // shift 1
   double emaThen = ema[InpTrendSlopeBars];      // shift 1 + slopeBars
   double slope   = emaNow - emaThen;
   if(dir == 1)
   {
      if(slope <= 0) return false;   // EMA200 not rising
   }
   else
   {
      if(slope >= 0) return false;   // EMA200 not falling
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
//| Day scope reset                                                   |
//+------------------------------------------------------------------+
void ResetDay()
{
   g_state    = ST_IDLE;
   g_bias     = 0;
   g_biasDone = false;
   g_touched  = false;
   g_tradesToday = 0;
}

//+------------------------------------------------------------------+
//| Bias from first two completed session bars (08:00 & 08:15 GMT)    |
//+------------------------------------------------------------------+
void ComputeBias()
{
   if(g_biasDone) return;

   int effStart = EffStartHour();

   datetime nowGmt = TimeCurrent() - (datetime)(InpServerUTC * 3600);
   MqlDateTime gdt;
   TimeToStruct(nowGmt, gdt);
   MqlDateTime mdt = gdt;
   mdt.hour = 0; mdt.min = 0; mdt.sec = 0;
   datetime midnightGmt = StructToTime(mdt);

   datetime bar1Gmt      = midnightGmt + effStart * 3600;    // 08:00 GMT
   datetime bar2Gmt      = bar1Gmt + 900;                    // 08:15 GMT
   datetime bar2CloseGmt = bar2Gmt + 900;                    // 08:30 GMT (2nd bar close)

   if(TimeCurrent() < bar2CloseGmt + (datetime)(InpServerUTC * 3600))
      return;   // second bias bar not yet closed

   int sh1 = iBarShift(g_symbol, PERIOD_M15, bar1Gmt + (datetime)(InpServerUTC * 3600), false);
   int sh2 = iBarShift(g_symbol, PERIOD_M15, bar2Gmt + (datetime)(InpServerUTC * 3600), false);
   if(sh1 < 0 || sh2 < 0 || sh1 <= sh2) return;

   double o1 = iOpen(g_symbol, PERIOD_M15, sh1);
   double c1 = iClose(g_symbol, PERIOD_M15, sh1);
   double o2 = iOpen(g_symbol, PERIOD_M15, sh2);
   double c2 = iClose(g_symbol, PERIOD_M15, sh2);
   if(o1 <= 0 || c1 <= 0 || o2 <= 0 || c2 <= 0) return;

   bool b1 = (c1 > o1);
   bool b2 = (c2 > o2);
   bool s1 = (c1 < o1);
   bool s2 = (c2 < o2);

   if(b1 && b2)       g_bias = 1;
   else if(s1 && s2)  g_bias = -1;
   else               g_bias = -2;

   if(g_bias == 1  && !InpAllowLong)  g_bias = -2;
   if(g_bias == -1 && !InpAllowShort) g_bias = -2;

   g_biasDone = true;
   g_state = (g_bias == 1 || g_bias == -1) ? ST_WAIT_TOUCH : ST_IDLE;

   Print("XETRA_BIAS | ", (g_bias == 1 ? "LONG" : (g_bias == -1 ? "SHORT" : "NONE")),
         " | bar1 O=", DoubleToString(o1, g_digits), " C=", DoubleToString(c1, g_digits),
         " | bar2 O=", DoubleToString(o2, g_digits), " C=", DoubleToString(c2, g_digits));
}

//+------------------------------------------------------------------+
//| Entry trigger state machine (runs on new M15 bar)                 |
//+------------------------------------------------------------------+
void RunEngine()
{
   if(!g_biasDone)
   {
      ComputeBias();
      return;
   }
   if(g_state == ST_IDLE) return;   // no bias for the day

   double o1 = iOpen(g_symbol, PERIOD_M15, 1);
   double c1 = iClose(g_symbol, PERIOD_M15, 1);
   double h1 = iHigh(g_symbol, PERIOD_M15, 1);
   double l1 = iLow(g_symbol, PERIOD_M15, 1);
   if(o1 <= 0 || c1 <= 0 || h1 <= 0 || l1 <= 0) return;

   double ema20 = GetEma20();
   if(ema20 <= 0) return;

   // Phase 1: pullback must touch EMA20 in bias direction
   if(g_state == ST_WAIT_TOUCH)
   {
      bool touch = (g_bias == 1) ? (l1 <= ema20) : (h1 >= ema20);
      if(touch)
      {
         g_state   = ST_WAIT_TRIGGER;
         g_touched = true;
      }
   }

   // Phase 2: a completed bar must close in bias direction -> enter next open
   if(g_state == ST_WAIT_TRIGGER)
   {
      bool closeOk = (g_bias == 1) ? (c1 > o1) : (c1 < o1);
      if(closeOk)
      {
         TryEntry(g_bias);
         // Re-arm: daily governor + single-position rule cap actual fills at 1
         g_state   = ST_WAIT_TOUCH;
         g_touched = false;
      }
   }
}

//+------------------------------------------------------------------+
//| Entry                                                             |
//+------------------------------------------------------------------+
void TryEntry(int dir)
{
   long spread = SymbolInfoInteger(g_symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return;

   if(!TrendGatePass(dir)) return;

   double atr = GetATR();
   if(atr <= 0) return;

   double entry = (dir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double sl = (dir == 1) ? entry - InpSlAtrMult * atr
                          : entry + InpSlAtrMult * atr;
   double risk = (dir == 1) ? entry - sl : sl - entry;
   if(risk <= 0) return;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   double tp = (dir == 1) ? entry + risk * InpTpRR : entry - risk * InpTpRR;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   string comment = "XETRA_" + ((dir == 1) ? "L" : "S");
   trade.SetExpertMagicNumber(InpMagic);
   bool ok = (dir == 1) ? trade.Buy(lots, g_symbol, entry, sl, tp, comment)
                        : trade.Sell(lots, g_symbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("XETRA_ENTRY_REJECTED | ", comment, " | ret=", trade.ResultRetcode());
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

   Print("XETRA_TRADE | ", g_symbol, " | ", (dir == 1 ? "BUY" : "SELL"),
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

   Print("XETRA_CLOSE | ", (g_tradeDir == 1) ? "BUY" : "SELL",
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
             "XETRA",
             IntegerToString(g_entryWeekday),
             IntegerToString(g_entryGmtHour),
             IntegerToString(g_entrySession),
             "XETRA_" + ((g_tradeDir == 1) ? "L" : "S"));
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
      Print("XETRA: FATAL - cannot select symbol ", g_symbol);
      return INIT_FAILED;
   }
   g_digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);

   g_hATR = iATR(g_symbol, PERIOD_M15, InpAtrPeriod);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("XETRA: FATAL - ATR handle failed");
      return INIT_FAILED;
   }

   g_hEMA20 = iMA(g_symbol, PERIOD_M15, InpEntryEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_hEMA20 == INVALID_HANDLE)
   {
      Print("XETRA: FATAL - pullback EMA handle failed");
      return INIT_FAILED;
   }

   if(InpUseTrendGate)
   {
      g_hEMA200 = iMA(g_symbol, PERIOD_M15, InpTrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hEMA200 == INVALID_HANDLE)
      {
         Print("XETRA: FATAL - trend EMA handle failed");
         return INIT_FAILED;
      }
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_logFile     = StringFormat("DE40X1_TRADES_%d.csv", InpMagic);
   g_lastBar     = 0;
   g_gmtDayKey   = 0;
   g_tradesToday = 0;
   ResetDay();

   Print("=== DE40 XETRA Harness v1.00 ===");
   Print("Symbol: ", g_symbol, " | Magic: ", InpMagic, " | TF: M15 | log: ", g_logFile);
   Print("Inputs [name = default (range)]:");
   Print("  InpXetraStartGMT = ", InpXetraStartGMT, " (0-23)");
   Print("  InpXetraEndGMT   = ", InpXetraEndGMT,   " (0-23)");
   Print("  InpDSTShift      = ", InpDSTShift,      " (0-2, 1=summer 07-09)");
   Print("  InpEntryEmaPeriod = ", InpEntryEmaPeriod, " (10-50)");
   Print("  InpTrendEmaPeriod = ", InpTrendEmaPeriod, " (150-300)");
   Print("  InpTrendSlopeBars = ", InpTrendSlopeBars, " (1-20)");
   Print("  InpUseTrendGate   = ", InpUseTrendGate ? "true" : "false", " (bool)");
   Print("  InpAtrPeriod      = ", InpAtrPeriod,      " (5-30)");
   Print("  InpSlAtrMult      = ", DoubleToString(InpSlAtrMult, 2), " (1.0-2.5)");
   Print("  InpTpRR           = ", DoubleToString(InpTpRR, 2), " (0.8-1.5)");
   Print("  InpAllowLong      = ", InpAllowLong ? "true" : "false", " (bool)");
   Print("  InpAllowShort     = ", InpAllowShort ? "true" : "false", " (bool)");
   Print("  InpRiskPct        = ", DoubleToString(InpRiskPct, 2), " (0.1-5.0)");
   Print("  InpMaxSpreadPts   = ", InpMaxSpreadPts,   " (10-2000)");
   Print("  InpMagic          = ", InpMagic,          " (4500)");
   Print("  InpMaxTradesDay   = ", InpMaxTradesDay,   " (1)");
   Print("XETRA session GMT: ", EffStartHour(), ":00-", EffEndHour(), ":00",
         " | Spread: ", SymbolInfoInteger(g_symbol, SYMBOL_SPREAD),
         " pts | Digits: ", g_digits);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hATR != INVALID_HANDLE)    IndicatorRelease(g_hATR);
   if(g_hEMA20 != INVALID_HANDLE)  IndicatorRelease(g_hEMA20);
   if(g_hEMA200 != INVALID_HANDLE) IndicatorRelease(g_hEMA200);
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   ManagePosition();   // per-tick: MFE/MAE + close detection

   datetime curBar = iTime(g_symbol, PERIOD_M15, 0);
   if(curBar == g_lastBar) return;
   g_lastBar = curBar;

   if(g_inPosition) return;   // one position at a time

   int wd, gh, gmo;
   ComputeGmt(TimeCurrent(), wd, gh, gmo);
   if(wd == 0 || wd == 6) return;   // weekend: no trading

   long dayKey = GmtDayKey(TimeCurrent());
   if(dayKey != g_gmtDayKey)
   {
      g_gmtDayKey = dayKey;
      ResetDay();
   }

   int sess = SessionBucket(gmo);
   if(sess == 0) return;   // outside Xetra session
   if(g_tradesToday >= InpMaxTradesDay) return;

   RunEngine();
}
//+------------------------------------------------------------------+
