//+------------------------------------------------------------------+
//| Module 8: DE40 Macro DXY Currency Beta Inversion Breakout        |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input double InpDxySlopeThreshBps = 5.0;   // OLS slope of DXY in bps per H1 bar
input int    InpStartHour         = 13;
input int    InpEndHour           = 15;
input int    InpEndMinute         = 30;
input double InpRiskPercent       = 0.5;
input long   InpMagic             = 260108;
input string InpComment           = "M8_DXYInv";

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

double GetDXYRegressionSlopeBps(int period)
{
   string sym = "USDX";
   if(!SymbolSelect(sym, true))
   {
      sym = "DXY";
      if(!SymbolSelect(sym, true)) return 0.0;   // no dollar index feed: stay flat
   }
   double sum_x = 0.0, sum_y = 0.0, sum_xy = 0.0, sum_x2 = 0.0;
   int n = 0;
   for(int i = period; i >= 1; i--)
   {
      double c = iClose(sym, PERIOD_H1, i);
      if(c <= 0.0) return 0.0;
      double x = (double)n;
      sum_x += x; sum_y += c; sum_xy += x * c; sum_x2 += x * x;
      n++;
   }
   if(n < 5) return 0.0;
   double denom = n * sum_x2 - sum_x * sum_x;
   if(denom == 0.0) return 0.0;
   double slope = (n * sum_xy - sum_x * sum_y) / denom;   // price per H1 bar
   double mean  = sum_y / n;
   if(mean <= 0.0) return 0.0;
   return slope / mean * 10000.0;                          // bps per H1 bar
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
   if(HasOpenPosition()) return;

   double slope_bps = GetDXYRegressionSlopeBps(20);
   if(slope_bps == 0.0) return;

   double atr = GetATR(1);
   if(atr <= 0.0) return;

   if(slope_bps < -InpDxySlopeThreshBps)       OpenBuyPosition(1.5 * atr, 2.0);   // dollar plummeting -> DAX bid
   else if(slope_bps > InpDxySlopeThreshBps)   OpenSellPosition(1.5 * atr, 2.0);  // dollar surging -> DAX offered
}
