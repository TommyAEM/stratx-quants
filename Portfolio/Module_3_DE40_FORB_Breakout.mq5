//+------------------------------------------------------------------+
//| Module 3: DE40 Frankfurt Opening Range Breakout (FORB)           |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input double InpBreakoutBufferPts = 6.0;
input double InpMinRangePts = 30.0;
input int    InpSessionOpenHour = 8;
input int    InpSessionCloseHour = 10;

void OnTick()
{
   if(!IsNewBar()) return;
   if(Hour() < InpSessionOpenHour || Hour() >= InpSessionCloseHour) return;
   double f_high = GetFrankfurtHigh();
   double f_low  = GetFrankfurtLow();
   if((f_high - f_low) >= InpMinRangePts)
   {
      if(Close[1] > f_high + InpBreakoutBufferPts) OpenBuyPosition();
      else if(Close[1] < f_low - InpBreakoutBufferPts) OpenSellPosition();
   }
}
