//+------------------------------------------------------------------+
//| Module 1: DE40 Volume Profile POC Reversion                      |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input double InpAtrThreshold = 48.0; // LL5_PIVOT_NEW_ALPHA Dynamic Volatility Floor
input double InpDeviationThreshold = 1.85;
input int    InpStartHour = 9;
input int    InpStartMin = 30;
input int    InpEndHour = 11;

void OnTick()
{
   if(!IsNewBar()) return;
   if(Hour() < InpStartHour || (Hour() == InpStartHour && Minute() < InpStartMin)) return;
   if(Hour() >= InpEndHour) return;
   double poc_level = iMA(_Symbol, _Period, 48, 0, MODE_EMA, PRICE_MEDIAN);
   double dev = MathAbs(Close[1] - poc_level);
   if(dev > InpDeviationThreshold * iATR(_Symbol, _Period, 14, 0))
   {
      if(Close[1] > poc_level) OpenSellPosition();
      else if(Close[1] < poc_level) OpenBuyPosition();
   }
}
