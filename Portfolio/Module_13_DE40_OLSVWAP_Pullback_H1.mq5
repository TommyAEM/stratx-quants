//+------------------------------------------------------------------+
//| Module 13: DE40 OLS Slope Pullback to Rolling VWAP (H1)          |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpOlsPeriod    = 20;
input int    InpVwapPeriod   = 20;
input double InpMinR2        = 0.70;
input double InpRiskPercent  = 0.5;
input long   InpMagic        = 260113;
input string InpComment      = "M13_OLSVWAP";

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

// Rolling VWAP computed natively (iCustom "VWAP" is NOT installed on the terminal).
double RollingVWAP(const string sym, ENUM_TIMEFRAMES tf, int period)
{
   double pv = 0.0, vv = 0.0;
   for(int i = 1; i <= period; i++)
   {
      double typical = (iHigh(sym, tf, i) + iLow(sym, tf, i) + iClose(sym, tf, i)) / 3.0;
      double vol     = (double)iVolume(sym, tf, i);
      pv += typical * vol;
      vv += vol;
   }
   if(vv <= 0.0) return 0.0;
   return pv / vv;
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

   // 1. Trend validity: OLS slope sign + R^2 > 0.70 (clean trend only)
   double slope, r2;
   ComputeLinReg(_Symbol, PERIOD_H1, InpOlsPeriod, slope, r2);
   bool is_uptrend   = (slope > 0.0 && r2 > InpMinR2);
   bool is_downtrend = (slope < 0.0 && r2 > InpMinR2);
   if(!is_uptrend && !is_downtrend) return;

   // 2. Rolling VWAP as the institutional fair-value pullback zone
   double vwap = RollingVWAP(_Symbol, PERIOD_H1, InpVwapPeriod);
   if(vwap <= 0.0) return;

   // 3. Entry: pullback touches VWAP, candle closes back on the trend side (2R target)
   double h1_low1   = iLow(_Symbol, PERIOD_H1, 1);
   double h1_high1  = iHigh(_Symbol, PERIOD_H1, 1);
   double h1_close1 = iClose(_Symbol, PERIOD_H1, 1);

   if(is_uptrend && h1_low1 <= vwap && h1_close1 > vwap)
   {
      double sl = vwap - 1.5 * atr_h1;
      ExecuteBuy(sl, h1_close1 + 2.0 * (h1_close1 - sl));
   }
   else if(is_downtrend && h1_high1 >= vwap && h1_close1 < vwap)
   {
      double sl = vwap + 1.5 * atr_h1;
      ExecuteSell(sl, h1_close1 - 2.0 * (sl - h1_close1));
   }
}
