//+------------------------------------------------------------------+
//| DE40_VPPOC_HARNESS.mq5                                           |
//| Standalone research harness: native volume-profile (tick-volume)  |
//| POC / VAH / VAL rejection for DE40 (Germany 40 / DAX).            |
//|                                                                    |
//| Module scope (cross-task contract): magic 4400 (VPPOC).            |
//| Self-contained single module; does NOT touch the host EA or any    |
//| sibling file.                                                       |
//|                                                                    |
//| TICK-VOLUME PROXY LIMITATION (documented):                         |
//|  MT5 does not expose real market/contract volume to EAs. The       |
//|  volume profile here is built from TICK VOLUME (MT5's count of     |
//|  price ticks per bar), which is a proxy of traded activity, not    |
//|  executed contracts. On CFD index symbols like GER40 the tick      |
//|  stream approximates activity but can be skewed by quote-churn and |
//|  is not a true volume number. POC/VAH/VAL derived from tick volume |
//|  are therefore approximation levels that MUST be re-validated      |
//|  against any available true-volume feed before promotion.          |
//|                                                                    |
//| Logic                                                              |
//|  - Profile built over the prior [InpLookbackDays] daily sessions   |
//|    (input 1..5, default 2) using M15 bars' tick volume, bucketed   |
//|    in fixed price buckets of InpBucketPts points (default 250 pts  |
//|    = 2.5 index points; conceptually ~0.25 x ATR14 on D1 scale).    |
//|  - POC = price bucket with maximum tick volume.                    |
//|  - VA  = InpVA_Pct% of total volume around POC (input 65..80,      |
//|    default 70) -> VAH (upper edge) / VAL (lower edge).             |
//|  - Entries (both fade to POC):                                     |
//|      (a) REJECT : price closes outside VA, tags beyond VAH/VAL by  |
//|          <= InpTagATR * ATR14(D1) (shallow extreme), then a bar    |
//|          closes back inside VA -> fade to POC.                     |
//|      (b) RECLAIM: price CLOSES outside VA for >= InpReclaimBars    |
//|          bars, then a bar closes back inside VA -> fade to POC.    |
//|  - SL beyond the tag extreme by InpSLBufATR * ATR14(D1).           |
//|  - TP = POC (both modes); fallback = fixed InpTP_RR if the POC     |
//|    target is on the wrong side of entry or too close.              |
//|  - One position at a time; spread guard; per-trade CSV on close    |
//|    with realized R and per-tick MFE/MAE (both in R units).         |
//|                                                                    |
//| Unit discipline (DJ30 lesson #4): all point quantities are raw     |
//| MT5 points (_Point); multiply by _Point for price (index points).  |
//| GER40.s: digits 2, _Point 0.01 -> 250 points = 2.5 index points.   |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 VPPOC — volume-profile POC/VAH/VAL rejection harness"

#include <Trade\Trade.mqh>
CTrade trade;

//---- trigger mode selector --------------------------------------------
enum ENUM_VP_TRIG
{
   TRIG_REJECT  = 0,  // (a) shallow reject (tag <= 0.2 ATR)
   TRIG_RECLAIM = 1,  // (b) reclaim (outside >=3 bars)
   TRIG_BOTH    = 2   // (a) or (b)
};

//---- inputs ------------------------------------------------------------
input group "=== Symbol Configuration ==="
input string InpSymbolOverride = "";          // Override symbol (empty=auto-detect)
input int    InpServerUTC      = 2;           // Server UTC offset (Vantage=2, PUPrime=3)

input group "=== Volume Profile ==="
input int    InpLookbackDays  = 2;            // Prior daily sessions in profile (1-5)
input int    InpBucketPts     = 250;          // Price bucket size, points (250 pts = 2.5 index pts ~0.25x ATR14 D1)
input int    InpVA_Pct        = 70;           // Value Area volume % around POC (65-80)
input int    InpATRPeriod     = 14;           // ATR period (D1 scale)

input group "=== Entry Triggers ==="
input ENUM_VP_TRIG InpTrigMode = TRIG_REJECT; // Trigger: a=reject, b=reclaim, both
input double InpTagATR      = 0.20;           // Mode a: max shallow tag beyond VAH/VAL (ATR14 D1)
input int    InpReclaimBars = 3;              // Mode b: closed-outside bars before reclaim
input double InpSLBufATR    = 0.30;           // Stop buffer beyond tag extreme (ATR14 D1)
input double InpTP_RR       = 1.0;            // Fixed-RR fallback when POC target unusable
input bool   InpFixedRROnly  = false;        // true = always fixed 1R TP (never POC target)
input double InpMinPocRR     = 0.0;          // >0 = require POC distance >= this x risk else fixed RR
input int    InpTimeStopBars = 0;            // >0 = market-close after N M15 bars held
input bool   InpFridayFlat   = false;        // true = no Friday entries; close open pos Friday >=16 GMT
input bool   InpAllowShort  = true;           // allow short (fade above VAH) setups
input bool   InpAllowLong   = true;           // allow long (fade below VAL) setups

input group "=== Session / Timing ==="
input int    InpStartGMT = 7;                 // Entries allowed from GMT hour (inclusive)
input int    InpEndGMT   = 17;                // Entries allowed until GMT hour (exclusive)

input group "=== Risk / Safety ==="
input double InpLots         = 0.10;          // Fixed volume per trade
input int    InpMaxSpreadPts = 400;           // Spread guard (points)
input int    InpMagic        = 4400;          // VPPOC magic (cross-task contract-fixed)
input int    InpColdStartSec = 30;            // Cold-start delay after attach (sec)

//---- globals -----------------------------------------------------------
int      g_hATR = INVALID_HANDLE;             // iATR(D1, InpATRPeriod)
string   g_activeSymbol = "";
datetime g_attachTime = 0;

// profile state (prior-session levels, frozen within a day)
double   g_d1ATR = 0;                         // ATR14(D1) in price units
double   g_poc = 0, g_vah = 0, g_val = 0;
bool     g_profileValid = false;
datetime g_profileDay = 0;                     // D1 open time the profile was built for

// M15 evaluation cadence
datetime g_lastM15 = 0;

// excursion state machine (relative to VAH/VAL, classified by bar close)
int      g_excSide = 0;                        // 0=inside, +1=above VAH, -1=below VAL
int      g_excBars = 0;                        // consecutive bars closed outside VA
double   g_excExtreme = 0;                     // extreme of current excursion (high if above, low if below)

// open-position state
bool     g_inPosition = false;
int      g_posDir = 0;                         // +1 long, -1 short
double   g_entryPrice = 0, g_sl = 0, g_tp = 0;
double   g_riskPts = 0;                        // initial risk in points
double   g_mfeR = 0, g_maeR = 0;               // per-tick max favorable / adverse excursion in R
datetime g_entryTime = 0;
int      g_entryDow = 0, g_entryGmtHour = 0;
string   g_entrySession = "";
string   g_entryComment = "";

//+------------------------------------------------------------------+
//| Symbol auto-detection (mirrors parent pattern)                    |
//+------------------------------------------------------------------+
string DetectDE40Symbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("VPPOC: override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string candidates[] = {
      "GER40", "GER40.cash", "GER40+", "DE40", "DE40+",
      "DAX40", "DAX", "Germany40", "DEU40", "DEU40.cash",
      "GER40m", "GER40fs", "DAX.fs", "DE40fs"
   };
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolSelect(candidates[i], true))
      {
         double bid = SymbolInfoDouble(candidates[i], SYMBOL_BID);
         if(bid > 0)
         {
            Print("VPPOC: detected symbol ", candidates[i], " bid=", bid);
            return candidates[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;
   Print("VPPOC: WARNING - no DE40 symbol found, using chart symbol ", _Symbol);
   return _Symbol;
}

//+------------------------------------------------------------------+
//| GMT DateTime conversion                                           |
//+------------------------------------------------------------------+
void GmtTime(datetime t, MqlDateTime &dt)
{
   TimeToStruct((datetime)((long)t - (long)InpServerUTC * 3600), dt);
}

//+------------------------------------------------------------------+
//| Session bucket label from GMT hour (DE40 sessions)                |
//+------------------------------------------------------------------+
string SessionBucket(int gmtHour)
{
   if(gmtHour < 7)  return "Asia";
   if(gmtHour < 8)  return "Frankfurt";
   if(gmtHour < 11) return "London";
   if(gmtHour < 13) return "Midday";
   if(gmtHour < 16) return "USOverlap";
   return "Late";
}

//+------------------------------------------------------------------+
//| ATR14 on D1 (last completed daily bar)                            |
//+------------------------------------------------------------------+
double GetD1ATR()
{
   if(g_hATR == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hATR, 0, 1, 1, buf) < 1) return 0;
   return buf[0];
}

//+------------------------------------------------------------------+
//| Volume profile construction over prior daily sessions             |
//+------------------------------------------------------------------+
bool BuildProfile()
{
   g_profileValid = false;
   g_poc = 0; g_vah = 0; g_val = 0;

   datetime d1Open = iTime(g_activeSymbol, PERIOD_D1, 0);
   if(d1Open <= 0) return false;

   // Window = [d1Open - N*24h, d1Open). The current (incomplete) session is
   // excluded, so the profile spans exactly the prior N daily sessions.
   // Weekend gaps contribute no M15 bars (no trading) and are skipped.
   datetime from = (datetime)((long)d1Open - (long)InpLookbackDays * 86400);

   MqlRates rates[];
   int got = CopyRates(g_activeSymbol, PERIOD_M15, from, d1Open, rates);
   if(got <= 10) return false;

   double mn = DBL_MAX, mx = -DBL_MAX;
   int cnt = 0;
   for(int i = 0; i < got; i++)
   {
      if(rates[i].time < from || rates[i].time >= d1Open) continue;
      if(rates[i].low  < mn) mn = rates[i].low;
      if(rates[i].high > mx) mx = rates[i].high;
      cnt++;
   }
   if(cnt <= 5) return false;

   double bucketSize = InpBucketPts * _Point;
   if(bucketSize <= 0) return false;
   int nb = (int)MathFloor((mx - mn) / bucketSize) + 2;
   if(nb < 2 || nb > 20000) return false;

   double vol[];
   ArrayResize(vol, nb);
   ArrayInitialize(vol, 0.0);

   for(int i = 0; i < got; i++)
   {
      if(rates[i].time < from || rates[i].time >= d1Open) continue;
      double typ = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      int idx = (int)MathFloor((typ - mn) / bucketSize);
      if(idx < 0)            idx = 0;
      if(idx >= nb)          idx = nb - 1;
      vol[idx] += (double)rates[i].tick_volume;
   }

   double total = 0;
   for(int i = 0; i < nb; i++) total += vol[i];
   if(total <= 0) return false;

   // POC = max-volume bucket
   int pocIdx = 0;
   for(int i = 1; i < nb; i++)
      if(vol[i] > vol[pocIdx]) pocIdx = i;

   // Value area: expand from POC by always adding the higher-volume neighbour
   int loIdx = pocIdx, hiIdx = pocIdx;
   double target = total * (double)InpVA_Pct / 100.0;
   double vaVol  = vol[pocIdx];
   while(vaVol < target && (loIdx > 0 || hiIdx < nb - 1))
   {
      double up = (hiIdx < nb - 1) ? vol[hiIdx + 1] : -1.0;
      double dn = (loIdx > 0)       ? vol[loIdx - 1] : -1.0;
      if(up < 0 && dn < 0) break;
      if(up >= dn) { hiIdx++; vaVol += vol[hiIdx]; }
      else         { loIdx--; vaVol += vol[loIdx]; }
   }

   g_poc = mn + (pocIdx + 0.5) * bucketSize;
   g_vah = mn + (hiIdx + 1)       * bucketSize;   // upper edge of top VA bucket
   g_val = mn + (loIdx)           * bucketSize;   // lower edge of bottom VA bucket

   if(g_vah <= g_val) return false;

   g_profileValid = true;
   g_profileDay   = d1Open;

   Print("VPPOC: profile built | bars=", cnt, " | buckets=", nb,
         " | POC=", DoubleToString(g_poc, _Digits),
         " | VAH=", DoubleToString(g_vah, _Digits),
         " | VAL=", DoubleToString(g_val, _Digits),
         " | bucket=", DoubleToString(bucketSize, _Digits), " pts=", InpBucketPts);
   return true;
}

//+------------------------------------------------------------------+
//| Entry execution                                                   |
//+------------------------------------------------------------------+
void TryEntry(int dir, string comment)
{
   if(g_inPosition) return;
   if(dir == +1 && !InpAllowLong)  return;
   if(dir == -1 && !InpAllowShort) return;

   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts)
   {
      Print("VPPOC: spread guard blocked (", spread, " > ", InpMaxSpreadPts, ") pts");
      return;
   }
   if(g_d1ATR <= 0) return;

   double entry = (dir == +1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK)
                              : SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
   if(entry <= 0) return;

   double sl = (dir == +1) ? g_excExtreme - InpSLBufATR * g_d1ATR
                           : g_excExtreme + InpSLBufATR * g_d1ATR;
   sl = NormalizeDouble(sl, _Digits);

   double risk = MathAbs(entry - sl);
   if(risk <= 0) return;
   if((dir == +1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   double riskPts = risk / _Point;

   // Primary target = POC; fallback = fixed RR (payoff-repair inputs).
   double tp;
   bool pocOk = false;
   if(!InpFixedRROnly)
   {
      double minRR = (InpMinPocRR > 0) ? InpMinPocRR : 0.25;
      if(dir == +1 && g_poc > entry && (g_poc - entry) >= minRR * risk) pocOk = true;
      if(dir == -1 && g_poc < entry && (entry - g_poc) >= minRR * risk) pocOk = true;
   }
   if(pocOk) tp = g_poc;
   else      tp = (dir == +1) ? entry + risk * InpTP_RR : entry - risk * InpTP_RR;
   tp = NormalizeDouble(tp, _Digits);

   double volStep = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MAX);
   double lots    = InpLots;
   if(volStep > 0) lots = MathFloor(lots / volStep) * volStep;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;

   bool ok = (dir == +1) ? trade.Buy(lots, g_activeSymbol, entry, sl, tp, comment)
                         : trade.Sell(lots, g_activeSymbol, entry, sl, tp, comment);
   if(!ok)
   {
      Print("VPPOC: order failed | ", comment, " | err=", GetLastError());
      return;
   }

   double fill = trade.ResultPrice();
   g_inPosition  = true;
   g_posDir      = dir;
   g_entryPrice  = (fill > 0) ? fill : entry;
   g_sl          = sl;
   g_tp          = tp;
   g_riskPts     = riskPts;
   g_mfeR        = 0;
   g_maeR        = 0;
   g_entryTime   = TimeCurrent();
   g_entryComment = comment;

   MqlDateTime gdt;
   GmtTime(g_entryTime, gdt);
   g_entryDow     = gdt.day_of_week;
   g_entryGmtHour = gdt.hour;
   g_entrySession = SessionBucket(gdt.hour);

   Print(comment, " | ", g_activeSymbol, " | ", (dir == +1) ? "BUY" : "SELL",
         " | entry=", DoubleToString(g_entryPrice, _Digits),
         " | sl=", DoubleToString(sl, _Digits),
         " | tp=", DoubleToString(tp, _Digits),
         " | risk=", DoubleToString(riskPts, 1), " pts (", DoubleToString(risk, _Digits), " px)");
}

//+------------------------------------------------------------------+
//| New-M15-bar evaluation: profile excursion state machine           |
//+------------------------------------------------------------------+
void EvaluateM15()
{
   double close = iClose(g_activeSymbol, PERIOD_M15, 1);
   double high  = iHigh(g_activeSymbol, PERIOD_M15, 1);
   double low   = iLow(g_activeSymbol, PERIOD_M15, 1);
   if(close <= 0) return;

   int barSide = 0;
   if(close > g_vah)      barSide = +1;
   else if(close < g_val) barSide = -1;

   if(barSide == +1)
   {
      if(g_excSide == +1) { g_excBars++; if(high > g_excExtreme) g_excExtreme = high; }
      else                { g_excSide = +1; g_excBars = 1; g_excExtreme = high; }
   }
   else if(barSide == -1)
   {
      if(g_excSide == -1) { g_excBars++; if(low < g_excExtreme) g_excExtreme = low; }
      else                { g_excSide = -1; g_excBars = 1; g_excExtreme = low; }
   }
   else // closed back inside VA
   {
      if(g_excSide == +1)
      {
         bool reject  = (InpTrigMode == TRIG_REJECT || InpTrigMode == TRIG_BOTH) &&
                        ((g_excExtreme - g_vah) <= InpTagATR * g_d1ATR);
         bool reclaim = (InpTrigMode == TRIG_RECLAIM || InpTrigMode == TRIG_BOTH) &&
                        (g_excBars >= InpReclaimBars);
         if(reject)       TryEntry(-1, "VPPOC_REJECT_SHORT");
         else if(reclaim) TryEntry(-1, "VPPOC_RECLAIM_SHORT");
         g_excSide = 0; g_excBars = 0; g_excExtreme = 0;
      }
      else if(g_excSide == -1)
      {
         bool reject  = (InpTrigMode == TRIG_REJECT || InpTrigMode == TRIG_BOTH) &&
                        ((g_val - g_excExtreme) <= InpTagATR * g_d1ATR);
         bool reclaim = (InpTrigMode == TRIG_RECLAIM || InpTrigMode == TRIG_BOTH) &&
                        (g_excBars >= InpReclaimBars);
         if(reject)       TryEntry(+1, "VPPOC_REJECT_LONG");
         else if(reclaim) TryEntry(+1, "VPPOC_RECLAIM_LONG");
         g_excSide = 0; g_excBars = 0; g_excExtreme = 0;
      }
      // g_excSide == 0: nothing to do
   }
}

//+------------------------------------------------------------------+
//| Find closing deal of our open position                            |
//+------------------------------------------------------------------+
bool FindExitDeal(double &price, datetime &time)
{
   price = 0; time = 0;
   if(!HistorySelect(g_entryTime, TimeCurrent() + 120)) return false;
   int n = HistoryDealsTotal();
   for(int i = n - 1; i >= 0; i--)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(dt == 0) continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != g_activeSymbol) continue;
      if(HistoryDealGetInteger(dt, DEAL_MAGIC) != (long)InpMagic) continue;
      ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt, DEAL_ENTRY);
      if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_INOUT)
      {
         price = HistoryDealGetDouble(dt, DEAL_PRICE);
         time  = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Per-trade CSV log on close (cross-task contract schema)           |
//+------------------------------------------------------------------+
void LogTradeClose(double exitPrice, datetime exitTime)
{
   if(g_entryPrice <= 0 || g_riskPts <= 0) return;

   double profitPts = (g_posDir == +1) ? (exitPrice - g_entryPrice) / _Point
                                       : (g_entryPrice - exitPrice) / _Point;
   double R       = profitPts / g_riskPts;
   string fname   = StringFormat("DE40X1_TRADES_%d.csv", InpMagic);

   bool needHeader = false;
  int h = FileOpen(fname, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
   {
      h = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      needHeader = true;
   }
   else
   {
      FileSeek(h, 0, SEEK_END);
      needHeader = (FileSize(h) <= 0);
   }
   if(h == INVALID_HANDLE)
   {
      Print("VPPOC: cannot open CSV ", fname, " err=", GetLastError());
      return;
   }

   if(needHeader)
      FileWrite(h, "time_open", "time_close", "side", "entry", "sl", "tp",
                   "exit_price", "R", "MFE_R", "MAE_R", "module",
                   "weekday", "gmt_hour", "session_bucket", "comment");

   string side = (g_posDir == +1) ? "BUY" : "SELL";
   FileWrite(h,
             (long)g_entryTime,
             (long)exitTime,
             side,
             DoubleToString(g_entryPrice, _Digits),
             DoubleToString(g_sl, _Digits),
             DoubleToString(g_tp, _Digits),
             DoubleToString(exitPrice, _Digits),
             DoubleToString(R, 4),
             DoubleToString(g_mfeR, 4),
             DoubleToString(g_maeR, 4),
             "VPPOC",
             g_entryDow,
             g_entryGmtHour,
             g_entrySession,
             g_entryComment);
   FileClose(h);

   Print("VPPOC: trade logged | ", side, " | exit=", DoubleToString(exitPrice, _Digits),
         " | R=", DoubleToString(R, 3),
         " | MFE=", DoubleToString(g_mfeR, 3),
         " | MAE=", DoubleToString(g_maeR, 3),
         " | file=", fname);
}

//+------------------------------------------------------------------+
//| Reset open-position state                                         |
//+------------------------------------------------------------------+
void ResetPosState()
{
   g_inPosition  = false;
   g_posDir      = 0;
   g_entryPrice  = 0;
   g_sl          = 0;
   g_tp          = 0;
   g_riskPts     = 0;
   g_mfeR        = 0;
   g_maeR        = 0;
   g_entryTime   = 0;
   g_entryDow    = 0;
   g_entryGmtHour = 0;
   g_entrySession = "";
   g_entryComment = "";
}
//+------------------------------------------------------------------+
//| Per-tick position management: MFE/MAE + close detection + CSV     |
//+------------------------------------------------------------------+
void ManagePosition()
{
   if(!g_inPosition) return;

   bool found = false;
   ulong openTk = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_activeSymbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
      { found = true; openTk = tk; break; }
   }

   if(!found)
   {
      double exitPrice = 0;
      datetime exitTime = 0;
      if(!FindExitDeal(exitPrice, exitTime))
         return;   // deal not yet flushed to history; re-check next tick
      LogTradeClose(exitPrice, exitTime);
      ResetPosState();
      return;
   }

   // payoff-repair exits: time stop + Friday flat
   if(InpTimeStopBars > 0 || InpFridayFlat)
   {
      int heldBars = (int)((TimeCurrent() - g_entryTime) / 900);
      MqlDateTime fg; GmtTime(TimeCurrent(), fg);
      bool fridayClose = InpFridayFlat && fg.day_of_week == 5 && fg.hour >= 16;
      if((InpTimeStopBars > 0 && heldBars >= InpTimeStopBars) || fridayClose)
      {
         if(trade.PositionClose(openTk))
            Print("VPPOC: payoff-repair exit | heldBars=", heldBars, " | friday=", fridayClose);
      }
   }
   // update MFE/MAE (R units), per tick
   double cur = (g_posDir == +1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_BID)
                                 : SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
   if(cur <= 0 || g_riskPts <= 0) return;
   double profitPts = (g_posDir == +1) ? (cur - g_entryPrice) / _Point
                                       : (g_entryPrice - cur) / _Point;
   double r = profitPts / g_riskPts;
   if(r > g_mfeR) g_mfeR = r;
   if(r < g_maeR) g_maeR = r;
}

//+------------------------------------------------------------------+
//| Initialization                                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   g_activeSymbol = DetectDE40Symbol();
   if(!SymbolSelect(g_activeSymbol, true))
   {
      Print("VPPOC: FATAL - cannot select symbol ", g_activeSymbol);
      return INIT_FAILED;
   }

   g_hATR = iATR(g_activeSymbol, PERIOD_D1, InpATRPeriod);
   if(g_hATR == INVALID_HANDLE)
   {
      Print("VPPOC: FATAL - D1 ATR handle failed");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_attachTime    = TimeCurrent();
   g_lastM15       = 0;
   g_profileDay    = 0;
   g_profileValid  = false;
   g_excSide       = 0;
   g_excBars       = 0;
   g_excExtreme    = 0;
   ResetPosState();

   Print("=== DE40 VPPOC Harness v1.00 (magic ", InpMagic, ") ===");
   Print("Symbol: ", g_activeSymbol);
   Print("LookbackDays: ", InpLookbackDays, " | BucketPts: ", InpBucketPts,
         " (", DoubleToString(InpBucketPts * _Point, _Digits), " px) | VA%: ", InpVA_Pct);
   Print("Trigger: ", InpTrigMode == TRIG_REJECT ? "reject" :
                        (InpTrigMode == TRIG_RECLAIM ? "reclaim" : "both"),
         " | TagATR: ", DoubleToString(InpTagATR, 2),
         " | ReclaimBars: ", InpReclaimBars,
         " | SLBufATR: ", DoubleToString(InpSLBufATR, 2));
   Print("Entry window (GMT): ", InpStartGMT, "..", InpEndGMT,
         " | Spread guard: ", InpMaxSpreadPts, " pts | Lots: ", DoubleToString(InpLots, 2));
   Print("CSV log: DE40X1_TRADES_", InpMagic, ".csv (terminal Files dir)");
   Print("NOTE: tick-volume proxy — POC/VAH/VAL approximate traded activity, not real volume.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hATR != INVALID_HANDLE) IndicatorRelease(g_hATR);
   g_hATR = INVALID_HANDLE;
}

//+------------------------------------------------------------------+
//| Main loop                                                         |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1) manage any open position on every tick (MFE/MAE + close logging)
   ManagePosition();
   if(g_inPosition) return;

   if(TimeCurrent() - g_attachTime < InpColdStartSec) return;

   // 2) refresh D1 ATR / profile at a new daily session boundary
   datetime d1Open = iTime(g_activeSymbol, PERIOD_D1, 0);
   if(d1Open != g_profileDay || !g_profileValid)
   {
      g_d1ATR = GetD1ATR();
      if(g_d1ATR <= 0) return;
      BuildProfile();
      if(!g_profileValid) return;
   }

   // 3) evaluate once per new completed M15 bar
   datetime m15 = iTime(g_activeSymbol, PERIOD_M15, 1);
   if(m15 <= 0 || m15 == g_lastM15) return;
   g_lastM15 = m15;

   // 4) timing gates (GMT, weekday)
   MqlDateTime gdt;
   GmtTime(TimeCurrent(), gdt);
   if(gdt.day_of_week == 0 || gdt.day_of_week == 6) return;
   if(InpFridayFlat && gdt.day_of_week == 5) return;
   int gmtHour = gdt.hour;
   if(gmtHour < InpStartGMT || gmtHour >= InpEndGMT) return;

   EvaluateM15();
}
//+------------------------------------------------------------------+
