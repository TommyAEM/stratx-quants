//+------------------------------------------------------------------+
//| DE40 Alpha Flow Module (StratX)                                  |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"

input double InpAtrThreshold = 15.0;
input int    InpSessionHours = 8;
input double InpFixedRiskDollars = 100.0; // 1% risk per trade on $10k account

void OnTick()
{
   if(!IsNewBar()) return;
   // H1 & H3 Fix: Session filter, ATR expansion floor & NFP news blackout
   if(Hour() < 9 || (Hour() == 9 && Minute() < 30)) return; // Prunes illiquid Asian overlap
   double atr_current = iATR(_Symbol, _Period, 14, 0);
   if(atr_current < 1.50 * InpAtrThreshold) return; // Prunes low-vol chop
   if(DayOfWeek() == 5 && Hour() == 12 && Minute() <= 45) return; // US NFP Blackout
   if(SignalBuy()) OpenBuyPosition();
}
