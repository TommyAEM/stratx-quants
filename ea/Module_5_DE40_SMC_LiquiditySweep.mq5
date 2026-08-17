//+------------------------------------------------------------------+
//| Module 5: DE40 Smart Money Liquidity Sweep & Order Block Entry   |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input double InpMinWickRatio = 0.65;
input int    InpStartHour = 8;
input int    InpEndHour = 10;

void OnTick()
{
   if(!IsNewBar()) return;
   if(Hour() < InpStartHour || Hour() >= InpEndHour) return;
   double asian_high = GetAsianSessionHigh();
   double asian_low  = GetAsianSessionLow();
   if(High[1] > asian_high && Close[1] < asian_high && GetUpperWickRatio(1) >= InpMinWickRatio)
      OpenSellPosition();
   else if(Low[1] < asian_low && Close[1] > asian_low && GetLowerWickRatio(1) >= InpMinWickRatio)
      OpenBuyPosition();
}
