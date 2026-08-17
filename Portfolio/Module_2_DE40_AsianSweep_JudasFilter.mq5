//+------------------------------------------------------------------+
//| Module 2: DE40 Asian Session Liquidity Sweep                     |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpStartHour       = 8;
input int    InpEndHour         = 10;
input int    InpEndMinute       = 30;
input long   InpMaxSpreadPoints = 15;
input double InpVolSpikeMult    = 2.0;
input double InpRiskPercent     = 0.5;
input long   InpMagic           = 260102;
input string InpComment         = "M2_Sweep";

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

void GetAsianRange(double &a_high, double &a_low)
{
   a_high = 0.0;
   a_low  = DBL_MAX;
   MqlDateTime now_dt;
   TimeToStruct(TimeCurrent(), now_dt);
   for(int i = 1; i < 300; i++)
   {
      datetime bt = iTime(_Symbol, _Period, i);
      if(bt == 0) break;
      MqlDateTime bdt;
      TimeToStruct(bt, bdt);
      if(bdt.day_of_year != now_dt.day_of_year) break;
      if(bdt.hour < 8)
      {
         double h = iHigh(_Symbol, _Period, i);
         double l = iLow(_Symbol, _Period, i);
         if(h > a_high) a_high = h;
         if(l < a_low)  a_low  = l;
      }
   }
   if(a_low == DBL_MAX) a_low = 0.0;
}

long GetAvgVolume(int bars)
{
   long sum_vol = 0;
   for(int i = 1; i <= bars; i++) sum_vol += iVolume(_Symbol, _Period, i);
   return sum_vol / bars;
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
   if(!InSession(InpStartHour, 0, InpEndHour, InpEndMinute)) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints) return;
   if(HasOpenPosition()) return;

   double atr = GetATR(1);
   if(atr <= 0.0) return;

   double a_high, a_low;
   GetAsianRange(a_high, a_low);
   if(a_high <= 0.0 || a_low <= 0.0) return;

   long   avg_vol = GetAvgVolume(20);
   long   vol1    = iVolume(_Symbol, _Period, 1);
   double high1   = iHigh(_Symbol, _Period, 1);
   double low1    = iLow(_Symbol, _Period, 1);
   double close1  = iClose(_Symbol, _Period, 1);

   // Judas swing: sweep of Asian range rejected back inside + volume spike
   if(high1 > a_high && close1 < a_high && vol1 > (long)(avg_vol * InpVolSpikeMult))
      OpenSellPosition((high1 - close1) + atr, 2.0);
   else if(low1 < a_low && close1 > a_low && vol1 > (long)(avg_vol * InpVolSpikeMult))
      OpenBuyPosition((close1 - low1) + atr, 2.0);
}
