//+------------------------------------------------------------------+
//| Module 1: DE40 Fair Value Gap & Inversion Mitigation             |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpStartHour     = 9;
input int    InpEndHour       = 11;
input int    InpEndMinute     = 30;
input int    InpFvgMaxAgeBars = 3;
input double InpRiskPercent   = 0.5;
input long   InpMagic         = 260101;
input string InpComment       = "M1_FVG";

CTrade   trade;
int      atr_handle    = INVALID_HANDLE;
int      ema_h4_handle = INVALID_HANDLE;
datetime g_last_bar_time = 0;

// Active FVG state machine
int      g_fvg_dir    = 0;      // +1 bullish, -1 bearish, 0 none
double   g_fvg_top    = 0.0;
double   g_fvg_bottom = 0.0;
datetime g_fvg_time   = 0;

bool IsNewBar()
{
   datetime cur_bar_time = iTime(_Symbol, _Period, 0);
   if(cur_bar_time == g_last_bar_time) return false;
   g_last_bar_time = cur_bar_time;
   return true;
}

void GetHourMin(int &hour, int &minute)
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   hour   = dt.hour;
   minute = dt.min;
}

bool InSession(int start_h, int start_m, int end_h, int end_m)
{
   int hour, minute;
   GetHourMin(hour, minute);
   int now_m  = hour * 60 + minute;
   return (now_m >= start_h * 60 + start_m && now_m <= end_h * 60 + end_m);
}

double GetATR(int shift)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(atr_handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

bool HtfBull()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(ema_h4_handle, 0, 0, 2, buf) < 2) return false;
   return (buf[0] > buf[1]);
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   return false;
}

double CalcLots(double sl_distance)
{
   double tick_val  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_val <= 0.0 || tick_size <= 0.0 || sl_distance <= 0.0) return 0.01;
   double risk_amt = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
   double lots     = NormalizeDouble(risk_amt / ((sl_distance / tick_size) * tick_val), 2);
   double min_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   return MathMax(min_lot, MathMin(max_lot, lots));
}

void OpenBuyPosition(double sl_dist, double rr)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - sl_dist, _Digits);
   double tp  = NormalizeDouble(ask + sl_dist * rr, _Digits);
   trade.Buy(CalcLots(sl_dist), _Symbol, 0.0, sl, tp, InpComment);
}

void OpenSellPosition(double sl_dist, double rr)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl  = NormalizeDouble(bid + sl_dist, _Digits);
   double tp  = NormalizeDouble(bid - sl_dist * rr, _Digits);
   trade.Sell(CalcLots(sl_dist), _Symbol, 0.0, sl, tp, InpComment);
}

int OnInit()
{
   trade.SetExpertMagicNumber((ulong)InpMagic);
   atr_handle    = iATR(_Symbol, _Period, 14);
   ema_h4_handle = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);
   if(atr_handle == INVALID_HANDLE || ema_h4_handle == INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;

   double atr = GetATR(1);
   if(atr <= 0.0) return;

   // --- 1. Manage active FVG state ---
   if(g_fvg_dir != 0)
   {
      double low1   = iLow(_Symbol, _Period, 1);
      double high1  = iHigh(_Symbol, _Period, 1);
      double close1 = iClose(_Symbol, _Period, 1);

      // Invalidation (becomes IFVG): close through the gap before mitigation
      if(g_fvg_dir ==  1 && close1 < g_fvg_bottom) { g_fvg_dir = 0; return; }
      if(g_fvg_dir == -1 && close1 > g_fvg_top)    { g_fvg_dir = 0; return; }

      // Staleness: institutional momentum is dead after N bars
      if(Bars(_Symbol, _Period, g_fvg_time, iTime(_Symbol, _Period, 0)) - 1 > InpFvgMaxAgeBars) { g_fvg_dir = 0; return; }

      // Mitigation entry: price retraced into the gap
      if(InSession(InpStartHour, 0, InpEndHour, InpEndMinute) && !HasOpenPosition())
      {
         if(g_fvg_dir == 1 && low1 <= g_fvg_top)
         {
            OpenBuyPosition((close1 - g_fvg_bottom) + 1.5 * atr, 2.0);
            g_fvg_dir = 0;
         }
         else if(g_fvg_dir == -1 && high1 >= g_fvg_bottom)
         {
            OpenSellPosition((g_fvg_top - close1) + 1.5 * atr, 2.0);
            g_fvg_dir = 0;
         }
      }
      return;
   }

   // --- 2. Detect fresh 3-candle FVG on closed bars (shifts 3..1) ---
   if(!InSession(InpStartHour, 0, InpEndHour, InpEndMinute)) return;

   double high3 = iHigh(_Symbol, _Period, 3);
   double low3  = iLow(_Symbol, _Period, 3);
   double high1 = iHigh(_Symbol, _Period, 1);
   double low1  = iLow(_Symbol, _Period, 1);

   if(high3 < low1 && HtfBull())         // bullish FVG aligned with H4 EMA50 bias
   {
      g_fvg_dir    = 1;
      g_fvg_bottom = high3;
      g_fvg_top    = low1;
      g_fvg_time   = iTime(_Symbol, _Period, 1);
   }
   else if(low3 > high1 && !HtfBull())   // bearish FVG aligned with H4 EMA50 bias
   {
      g_fvg_dir    = -1;
      g_fvg_bottom = high1;
      g_fvg_top    = low3;
      g_fvg_time   = iTime(_Symbol, _Period, 1);
   }
}
