//+------------------------------------------------------------------+
//| Module 4: DE40 VWAP Volatility Squeeze & Dispersion Expansion    |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input double InpSigmaExpansion = 2.2;
input int    InpStartHour = 13;
input int    InpStartMin = 30;
input int    InpEndHour = 17;

void OnTick()
{
   if(!IsNewBar()) return;
   if(Hour() < InpStartHour || (Hour() == InpStartHour && Minute() < InpStartMin)) return;
   if(Hour() >= InpEndHour) return;
   double vwap = CalculateDailyVWAP();
   double std_dev = CalculateVWAPStdDev(vwap);
   if(Close[1] > vwap + InpSigmaExpansion * std_dev) OpenBuyPosition();
   else if(Close[1] < vwap - InpSigmaExpansion * std_dev) OpenSellPosition();
}
