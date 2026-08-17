//+------------------------------------------------------------------+
//| Module 11: DE40 Fib OLS Trend Pullback (H1 Swing)                |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpSwingLookback = 50;     // bars for swing high/low detection
input int    InpOlsPeriod     = 20;     // OLS trend window (H1 closes)
input double InpMinR2         = 0.70;   // minimum R-squared for a valid trend
input double InpFibLevel      = 0.618;  // pullback entry level
input double InpRiskPercent   = 0.5;
input long   InpMagic         = 260111;
input string InpComment       = "M11_FibOLS";

CTrade   trade;
int      atr_h1_handle = INVALID_HANDLE;
datetime g_last_bar_time = 0;

bool IsNewBar()
{
   datetime cur_bar_time = iTime(_Symbol, _Period, 0);
   if(cur_bar_time == g_last_bar_time) return false;
   g_last_bar_time = cur_bar_time;
   return true;
}

double GetH1ATR(int shift)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(atr_h1_handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

// OLS trend fit over closed bars. MQL5 has NO native LinearReg function - compute it.
void ComputeLinReg(const string sym, ENUM_TIMEFRAMES tf, int period, double &slope, double &r2)
{
   slope = 0.0;
   r2    = 0.0;
   double sum_x = 0.0, sum_y = 0.0, sum_xy = 0.0, sum_x2 = 0.0, sum_y2 = 0.0;
   int n = 0;
   for(int i = period; i >= 1; i--)
   {
      double c = iClose(sym, tf, i);
      if(c <= 0.0) return;
      double x = (double)n;
      sum_x += x; sum_y += c; sum_xy += x * c; sum_x2 += x * x; sum_y2 += c * c;
      n++;
   }
   if(n < 5) return;
   double denom = n * sum_x2 - sum_x * sum_x;
   if(denom == 0.0) return;
   slope = (n * sum_xy - sum_x * sum_y) / denom;
   double r_denom = denom * (n * sum_y2 - sum_y * sum_y);
   if(r_denom <= 0.0) return;
   double r = (n * sum_xy - sum_x * sum_y) / MathSqrt(r_denom);
   r2 = r * r;
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

void ExecuteBuy(double sl_price, double tp_price)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(ask - sl_price <= 0.0 || tp_price <= ask) return;
   trade.Buy(CalcLots(ask - sl_price), _Symbol, 0.0,
             NormalizeDouble(sl_price, _Digits), NormalizeDouble(tp_price, _Digits), InpComment);
}

void ExecuteSell(double sl_price, double tp_price)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(sl_price - bid <= 0.0 || tp_price >= bid) return;
   trade.Sell(CalcLots(sl_price - bid), _Symbol, 0.0,
              NormalizeDouble(sl_price, _Digits), NormalizeDouble(tp_price, _Digits), InpComment);
}

int OnInit()
{
   trade.SetExpertMagicNumber((ulong)InpMagic);
   atr_h1_handle = iATR(_Symbol, PERIOD_H1, 14);
   if(atr_h1_handle == INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasOpenPosition()) return;

   double atr_h1 = GetH1ATR(1);
   if(atr_h1 <= 0.0) return;

   // 1. Trend direction & validity (OLS slope + R^2 on H1)
   double slope, r2;
   ComputeLinReg(_Symbol, PERIOD_H1, InpOlsPeriod, slope, r2);
   bool is_uptrend   = (slope > 0.0 && r2 > InpMinR2);
   bool is_downtrend = (slope < 0.0 && r2 > InpMinR2);
   if(!is_uptrend && !is_downtrend) return;

   // 2. Dynamic Fibonacci retracement zone (H1 swing, closed bars)
   int high_idx = iHighest(_Symbol, PERIOD_H1, MODE_HIGH, InpSwingLookback, 1);
   int low_idx  = iLowest(_Symbol, PERIOD_H1, MODE_LOW, InpSwingLookback, 1);
   if(high_idx < 0 || low_idx < 0) return;
   double swing_high = iHigh(_Symbol, PERIOD_H1, high_idx);
   double swing_low  = iLow(_Symbol, PERIOD_H1, low_idx);
   double range = swing_high - swing_low;
   if(range <= 0.0) return;

   double h1_low1   = iLow(_Symbol, PERIOD_H1, 1);
   double h1_high1  = iHigh(_Symbol, PERIOD_H1, 1);
   double h1_close1 = iClose(_Symbol, PERIOD_H1, 1);
   double h1_open1  = iOpen(_Symbol, PERIOD_H1, 1);

   // 3. Institutional entry: fib pierce + structural rejection close (NO blind limits)
   if(is_uptrend)
   {
      double fib = swing_high - (range * InpFibLevel);
      if(h1_low1 <= fib && h1_close1 > h1_open1 && h1_close1 > fib)
         ExecuteBuy(swing_low - 1.5 * atr_h1, swing_high + range * 0.5);   // target 1.5x extension
   }
   else if(is_downtrend)
   {
      double fib = swing_low + (range * InpFibLevel);
      if(h1_high1 >= fib && h1_close1 < h1_open1 && h1_close1 < fib)
         ExecuteSell(swing_high + 1.5 * atr_h1, swing_low - range * 0.5);
   }
}
