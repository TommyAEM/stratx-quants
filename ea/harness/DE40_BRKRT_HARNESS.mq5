//+------------------------------------------------------------------+
//| DE40_BRKRT_HARNESS.mq5                                            |
//| Break-Retest Continuation (BRKRT) — standalone research harness   |
//| DE40 (Germany 40 / DAX) on M15. Magic base: 4100.                 |
//| CSV: DE40X1_TRADES_4100.csv (terminal Files dir).                 |
//|                                                                    |
//| Logic:                                                             |
//|   break   = M15 close beyond HH/LL of lookback                      |
//|   retest  = price returns within tol x breakout range within N bars |
//|   trigger = close beyond retest candle extreme in breakout dir      |
//|   gate    = price vs EMA AND EMA slope sign (ablation toggle)       |
//|   SL      = retest extreme +/- ATR(14,M15) x mult                   |
//|   TP      = fixed RR                                                |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 BRKRT — Break-Retest continuation w/ native EMA trend gate (M15)"

#include <Trade\Trade.mqh>
CTrade trade;

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "=== Symbol & Time ==="
input string InpSymbolOverride = "";   // Override symbol (empty=auto-detect)
input int    InpServerUTC      = 2;    // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== Break-Retest Geometry (M15) ==="
input int    InpLookback       = 60;   // Structure lookback bars (20-100)
input double InpRetestTol      = 0.4;  // Retest tolerance x breakout range (0.2-0.6)
input int    InpRetestBars     = 8;    // Max bars for retest after break (3-15)

input group "=== Trend Gate (ablation) ==="
input bool   InpUseTrendGate   = true; // Ablation: false = no EMA trend gate
input int    InpTrendEmaPeriod = 200;  // Trend EMA period (150-300)
input int    InpTrendSlopeBars = 5;    // EMA slope lookback bars for sign (1-20)
input group "=== Volatility Regime Gate (atr_pct) ==="
input bool   InpGateAtrPct   = false; // require M15 ATR14 pct within [min,max]
input double InpAtrPctMin    = 0.0;   // min ATR percentile (0-100)
input double InpAtrPctMax    = 100.0; // max ATR percentile (0-100)


input group "=== Stops & Targets ==="
input int    InpAtrPeriod      = 14;   // ATR period (M15)
input double InpSlAtrMult      = 2.0;  // SL = retest extreme +/- this x ATR (1.5-3.0)
input double InpTpRR           = 1.0;  // Fixed take-profit reward:risk

input group "=== Sessions (GMT) ==="
input int    InpSessionMask    = 7;    // bit0=Frankfurt, bit1=London, bit2=USOverlap
input bool   InpAllowLong      = true;  // allow long entries
input bool   InpAllowShort     = true;  // allow short entries
input int    InpFrankStartGMT  = 7;    // Frankfurt start hour GMT
input int    InpFrankEndGMT    = 10;   // Frankfurt end hour GMT
input int    InpLdnStartGMT    = 7;    // London start hour GMT
input int    InpLdnEndGMT      = 10;   // London end hour GMT
input int    InpUSStartGMT     = 13;   // US overlap start hour GMT
input int    InpUSEndGMT       = 16;   // US overlap end hour GMT

input group "=== Risk & Safety ==="
input double InpRiskPct        = 1.0;  // Risk per trade (% of balance)
input int    InpMaxSpreadPts   = 500;  // Max spread (points) to allow entry
input int    InpMagic          = 4100; // Expert magic number (BRKRT base)
input int    InpMaxTradesDay   = 5;    // Daily trade governor

//+------------------------------------------------------------------+
//| Constants & globals                                               |
//+------------------------------------------------------------------+
#define ST_SCAN   0
#define ST_RETEST 1

// Setup state (break -> retest -> trigger)
int      g_state          = ST_SCAN;
int      g_dir            = 0;       // +1 long, -1 short
double   g_level          = 0;       // breakout level (rangeHi for long, rangeLo for short)
double   g_rangeHi        = 0;
double   g_rangeLo        = 0;
double   g_bRange         = 0;       // breakout range = rangeHi - rangeLo
double   g_pullExtreme    = 0;       // retest extreme (lowest low for long, highest high for short)
double   g_retestHi       = 0;       // retest candle high
double   g_retestLo       = 0;       // retest candle low
bool     g_retestSat      = false;   // price has returned within tolerance
int      g_barsSinceBreak = 0;

// Position state (single position, magic 4100)
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
double   g_atrPct       = 0;      // M15 ATR14 percentile (0-100) at entry


//+------------------------------------------------------------------+
//| Symbol auto-detection                                             |
//+------------------------------------------------------------------+
string DetectSymbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("BRKRT: override '", InpSymbolOverride, "' not found, auto-detecting");
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
            Print("BRKRT: detected symbol ", cand[i]);
            return cand[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("BRKRT: WARNING - no DE40 symbol found, using chart symbol ", _Symbol);
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

// Session bucket (GMT): 1 = Frankfurt, 2 = London, 4 = US overlap, 0 = OOH
int SessionBucket(int gmtMinOfDay)
{
   if((InpSessionMask & 1) != 0 &&
      gmtMinOfDay >= InpFrankStartGMT * 60 && gmtMinOfDay < InpFrankEndGMT * 60)
      return 1;
   if((InpSessionMask & 2) != 0 &&
      gmtMinOfDay >= InpLdnStartGMT * 60 && gmtMinOfDay < InpLdnEndGMT * 60)
      return 2;
   if((InpSessionMask & 4) != 0 &&
      gmtMinOfDay >= InpUSStartGMT * 60 && gmtMinOfDay < InpUSEndGMT * 60)
      return 4;
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

// M15 ATR14 percentile (0-100) over last 500 completed bars (series indexing)
double ComputeAtrPct()
{
   double cur = GetATR();
   if(cur <= 0 || g_hATR == INVALID_HANDLE) return 0;
   double ab[];
   ArraySetAsSeries(ab, true);
   int n = CopyBuffer(g_hATR, 0, 1, 500, ab);
   if(n <= 0) return 0;
   int le = 0;
   for(int i = 0; i < n; i++) if(ab[i] <= cur) le++;
   return 100.0 * (double)le / (double)n;
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
   g_state          = ST_SCAN;
   g_dir            = 0;
   g_level          = 0;
   g_rangeHi        = 0;
   g_rangeLo        = 0;
   g_bRange         = 0;
   g_pullExtreme    = 0;
   g_retestHi       = 0;
   g_retestLo       = 0;
   g_retestSat      = false;
   g_barsSinceBreak = 0;
}

void ArmSetup(int dir, double rangeHi, double rangeLo)
{
   if(dir == 1 && !InpAllowLong)   return;
   if(dir == -1 && !InpAllowShort) return;
   g_state         = ST_RETEST;
   g_dir           = dir;
   g_rangeHi       = rangeHi;
   g_rangeLo       = rangeLo;
   g_bRange        = rangeHi - rangeLo;
   g_level         = (dir == 1) ? rangeHi : rangeLo;
   g_pullExtreme   = (dir == 1) ? 1.0e300 : -1.0e300;
   g_retestHi      = 0;
   g_retestLo      = 0;
   g_retestSat     = false;
   g_barsSinceBreak = 0;
}

//+------------------------------------------------------------------+
//| Break-retest state machine (runs on new M15 bar)                 |
//+------------------------------------------------------------------+
void RunEngine()
{
   double c1 = iClose(g_symbol, PERIOD_M15, 1);
   double h1 = iHigh(g_symbol, PERIOD_M15, 1);
   double l1 = iLow(g_symbol, PERIOD_M15, 1);
   if(c1 <= 0 || h1 <= 0 || l1 <= 0) return;

   if(g_state == ST_SCAN)
   {
      int count = InpLookback;
      double hi[], lo[];
      ArraySetAsSeries(hi, true);
      ArraySetAsSeries(lo, true);
      if(CopyHigh(g_symbol, PERIOD_M15, 2, count, hi) < count) return;
      if(CopyLow(g_symbol, PERIOD_M15, 2, count, lo) < count) return;
      double rangeHi = hi[0], rangeLo = lo[0];
      for(int i = 1; i < count; i++)
      {
         if(hi[i] > rangeHi) rangeHi = hi[i];
         if(lo[i] < rangeLo) rangeLo = lo[i];
      }
      if(c1 > rangeHi) ArmSetup(1, rangeHi, rangeLo);
      else if(c1 < rangeLo) ArmSetup(-1, rangeHi, rangeLo);
      return;
   }

   // --- RETEST phase ---
   g_barsSinceBreak++;
   if(g_barsSinceBreak > InpRetestBars) { ResetSetup(); return; }

   if(g_dir == 1)   // bullish break: pullback low retests the broken high
   {
      // invalidation: close back through the whole tolerance band
      if(c1 < g_level - InpRetestTol * g_bRange) { ResetSetup(); return; }
      if(l1 < g_pullExtreme) { g_pullExtreme = l1; g_retestHi = h1; g_retestLo = l1; }
      g_retestSat = (g_pullExtreme <= g_level + InpRetestTol * g_bRange);
      if(g_retestSat && c1 > g_retestHi) { TryEntry(1); ResetSetup(); return; }
   }
   else            // bearish break: pullback high retests the broken low
   {
      if(c1 > g_level + InpRetestTol * g_bRange) { ResetSetup(); return; }
      if(h1 > g_pullExtreme) { g_pullExtreme = h1; g_retestHi = h1; g_retestLo = l1; }
      g_retestSat = (g_pullExtreme >= g_level - InpRetestTol * g_bRange);
      if(g_retestSat && c1 < g_retestLo) { TryEntry(-1); ResetSetup(); return; }
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

   g_atrPct = ComputeAtrPct();
   if(InpGateAtrPct && (g_atrPct < InpAtrPctMin || g_atrPct > InpAtrPctMax)) return;


   double atr = GetATR();
   if(atr <= 0) return;

   double entry = (dir == 1) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double sl = (dir == 1) ? g_pullExtreme - InpSlAtrMult * atr
                          : g_pullExtreme + InpSlAtrMult * atr;
   double risk = (dir == 1) ? entry - sl : sl - entry;
   if(risk <= 0) return;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   double tp = (dir == 1) ? entry + risk * InpTpRR : entry - risk * InpTpRR;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   string comment = "BRKRT_" + ((dir == 1) ? "L" : "S");
   trade.SetExpertMagicNumber(InpMagic);
   bool ok = (dir == 1) ? trade.Buy(lots, g_symbol, entry, sl, tp, comment)
                        : trade.Sell(lots, g_symbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("BRKRT_ENTRY_REJECTED | ", comment, " | ret=", trade.ResultRetcode());
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

   Print("BRKRT_TRADE | ", g_symbol, " | ", (dir == 1 ? "BUY" : "SELL"),
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

   Print("BRKRT_CLOSE | ", (g_tradeDir == 1) ? "BUY" : "SELL",
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
   g_atrPct     = 0;

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
                "session_bucket", "comment", "atr_pct");

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
             "BRKRT",
             IntegerToString(g_entryWeekday),
             IntegerToString(g_entryGmtHour),
             IntegerToString(g_entrySession),
             "BRKRT_" + ((g_tradeDir == 1) ? "L" : "S"),
             DoubleToString(g_atrPct, 4));

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
      Print("BRKRT: FATAL - cannot select symbol ", g_symbol);
      return INIT_FAILED;
   }
   g_digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);

   g_hATR = iATR(g_symbol, PERIOD_M15, InpAtrPeriod);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("BRKRT: FATAL - ATR handle failed");
      return INIT_FAILED;
   }
   if(InpUseTrendGate)
   {
      g_hEMA = iMA(g_symbol, PERIOD_M15, InpTrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hEMA == INVALID_HANDLE)
      {
         Print("BRKRT: FATAL - trend EMA handle failed");
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

   Print("=== DE40 BRKRT Harness v1.00 ===");
   Print("Symbol: ", g_symbol, " | Magic: ", InpMagic, " | TF: M15 | log: ", g_logFile);
   Print("Lookback: ", InpLookback, " | RetestTol: ", DoubleToString(InpRetestTol, 2),
         " | RetestBars: ", InpRetestBars);
   Print("TrendGate: ", InpUseTrendGate ? "ON" : "OFF",
         " | EMA: ", InpTrendEmaPeriod, " | SlopeBars: ", InpTrendSlopeBars);
   Print("SL ATR x", DoubleToString(InpSlAtrMult, 2),
         " | TP RR: ", DoubleToString(InpTpRR, 2));
   Print("Sessions: Frank ", InpFrankStartGMT, "-", InpFrankEndGMT,
         " | Ldn ", InpLdnStartGMT, "-", InpLdnEndGMT,
         " | US ", InpUSStartGMT, "-", InpUSEndGMT,
         " GMT | mask=", InpSessionMask);
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
   if(curBar == g_lastBar) return;
   g_lastBar = curBar;

   if(g_inPosition) return;   // one position at a time

   int wd, gh, gmo;
   ComputeGmt(TimeCurrent(), wd, gh, gmo);
   if(wd == 0 || wd == 6) { if(g_state != ST_SCAN) ResetSetup(); return; }

   long dayKey = (long)g_gmtDayFromGmt(TimeCurrent());
   if(dayKey != g_gmtDayKey)
   {
      g_gmtDayKey  = dayKey;
      g_tradesToday = 0;
      if(g_state != ST_SCAN) ResetSetup();
   }

   int sess = SessionBucket(gmo);
   if(sess == 0) { if(g_state != ST_SCAN) ResetSetup(); return; }
   if(g_tradesToday >= InpMaxTradesDay) return;

   RunEngine();
}

// GMT YYYYMMDD key for daily rollover (offset-aware via InpServerUTC)
long g_gmtDayFromGmt(datetime t)
{
   datetime gmt = t - (datetime)(InpServerUTC * 3600);
   MqlDateTime dt;
   TimeToStruct(gmt, dt);
   return (long)dt.year * 10000 + (long)dt.mon * 100 + (long)dt.day;
}
//+------------------------------------------------------------------+
