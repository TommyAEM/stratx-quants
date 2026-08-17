//+------------------------------------------------------------------+
//| Module 2: DE40 OLS Linear Regression True Slope                  |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input int    InpRegressionPeriod = 24;
input double InpMinRSquared = 0.75;
input double InpMinSlope = 2.80;
input int    InpStartHour = 12;
input int    InpEndHour = 16;

void OnTick()
{
   if(!IsNewBar()) return;
   if(Hour() < InpStartHour || Hour() >= InpEndHour) return;
   double slope = 0.0, r2 = 0.0;
   CalculateLinearRegression(InpRegressionPeriod, slope, r2);
   if(r2 >= InpMinRSquared)
   {
      if(slope >= InpMinSlope) OpenBuyPosition();
      else if(slope <= -InpMinSlope) OpenSellPosition();
   }
}
