//+------------------------------------------------------------------+
//| Module 10: DE40 GMM Regime 2 High-Velocity Trend Expansion       |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input double InpAtrExpansionMult = 1.5;   // ATR(14) > 1.5x ATR(50) = Regime-2 velocity proxy
input int    InpStartHour        = 10;
input int    InpEndHour          = 14;
input int    InpEndMinute        = 0;
input double InpRiskPercent      = 0.5;
input long   InpMagic            = 260110;
input string InpComment          = "M10_RegimeMom";

CTrade   trade;
int      atr_handle       = INVALID_HANDLE;
int      atr_slow_handle  = INVALID_HANDLE;
int      ema_fast_handle  = INVALID_HANDLE;
int      ema_slow_handle  = INVALID_HANDLE;
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

double GetBuf(int handle, int shift)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

bool IsHighVolExpansion()
{
   double atr_fast = GetBuf(atr_handle, 1);
   double atr_slow = GetBuf(atr_slow_handle, 1);
   return (atr_slow > 0.0 && atr_fast > InpAtrExpansionMult * atr_slow);   // Python GMM Regime-2 proxy
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
   atr_handle      = iATR(_Symbol, _Period, 14);
   atr_slow_handle = iATR(_Symbol, _Period, 50);
   ema_fast_handle = iMA(_Symbol, _Period, 9, 0, MODE_EMA, PRICE_CLOSE);
   ema_slow_handle = iMA(_Symbol, _Period, 21, 0, MODE_EMA, PRICE_CLOSE);
   if(atr_handle == INVALID_HANDLE || atr_slow_handle == INVALID_HANDLE ||
      ema_fast_handle == INVALID_HANDLE || ema_slow_handle == INVALID_HANDLE)
      return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(!InSession(InpStartHour, 0, InpEndHour, InpEndMinute)) return;
   if(HasOpenPosition()) return;
   if(!IsHighVolExpansion()) return;   // only trade Regime-2 velocity expansion

   double ema_fast = GetBuf(ema_fast_handle, 1);
   double ema_slow = GetBuf(ema_slow_handle, 1);
   double close1   = iClose(_Symbol, _Period, 1);
   double atr      = GetBuf(atr_handle, 1);
   if(atr <= 0.0) return;

   if(ema_fast > ema_slow && close1 > ema_fast)        OpenBuyPosition(1.5 * atr, 2.0);
   else if(ema_fast < ema_slow && close1 < ema_fast)   OpenSellPosition(1.5 * atr, 2.0);
}
