//+------------------------------------------------------------------+
//| Module 3: DE40 Statistical Z-Score Chop Fade                     |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input double InpZScoreThreshold = 2.2;
input double InpMinChop         = 50.0;
input int    InpStartHour       = 10;
input int    InpStartMinute     = 30;
input int    InpEndHour         = 14;
input int    InpEndMinute       = 0;
input double InpRiskPercent     = 0.5;
input long   InpMagic           = 260103;
input string InpComment         = "M3_ZScore";

CTrade   trade;
int      atr_handle = INVALID_HANDLE;
datetime g_last_bar_time = 0;

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

double CalcCHOP(int period)
{
   double sum_tr = 0.0, highest = 0.0, lowest = DBL_MAX;
   for(int i = 1; i <= period; i++)
   {
      double h  = iHigh(_Symbol, _Period, i);
      double l  = iLow(_Symbol, _Period, i);
      double pc = iClose(_Symbol, _Period, i + 1);
      sum_tr += MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      if(h > highest) highest = h;
      if(l < lowest)  lowest  = l;
   }
   double range = highest - lowest;
   if(range <= 0.0 || sum_tr <= 0.0) return 100.0;
   return 100.0 * MathLog10(sum_tr / range) / MathLog10((double)period);
}

double CalcZScore(int period)
{
   double sum = 0.0, sum2 = 0.0;
   for(int i = 1; i <= period; i++)
   {
      double c = iClose(_Symbol, _Period, i);
      sum  += c;
      sum2 += c * c;
   }
   double mean = sum / period;
   double var  = sum2 / period - mean * mean;
   if(var <= 0.0) return 0.0;
   return (iClose(_Symbol, _Period, 1) - mean) / MathSqrt(var);
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
   atr_handle = iATR(_Symbol, _Period, 14);
   if(atr_handle == INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(!InSession(InpStartHour, InpStartMinute, InpEndHour, InpEndMinute)) return;
   if(HasOpenPosition()) return;

   if(CalcCHOP(14) < InpMinChop) return;   // trending market: Z-Score fades forbidden

   double atr = GetATR(1);
   if(atr <= 0.0) return;

   double z = CalcZScore(24);
   if(z > InpZScoreThreshold)        OpenSellPosition(1.5 * atr, 2.0);
   else if(z < -InpZScoreThreshold)  OpenBuyPosition(1.5 * atr, 2.0);
}