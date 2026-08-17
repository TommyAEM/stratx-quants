//+------------------------------------------------------------------+
//| Module 14: DE40 SuperTrend Momentum Shift + MACD Confirm (H4)    |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpStPeriod     = 10;
input double InpStMult       = 3.0;
input int    InpStBars       = 120;    // sequential SuperTrend build window
input double InpRiskPercent  = 0.5;
input long   InpMagic        = 260114;
input string InpComment      = "M14_STMACD";

CTrade   trade;
int      macd_h4_handle = INVALID_HANDLE;
int      atr_h4_handle  = INVALID_HANDLE;
datetime g_last_bar_time = 0;

bool IsNewBar()
{
   datetime cur_bar_time = iTime(_Symbol, _Period, 0);
   if(cur_bar_time == g_last_bar_time) return false;
   g_last_bar_time = cur_bar_time;
   return true;
}

double GetBuf(int handle, int buffer_no, int shift)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, buffer_no, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

// Native SuperTrend (ATR ratchet bands). iCustom "SuperTrend" is NOT installed on the terminal.
// st_dir: +1 = bullish (price above trailing lower band), -1 = bearish.
void ComputeSuperTrend(const string sym, ENUM_TIMEFRAMES tf, int period, double mult,
                       int bars, double &st_val, int &st_dir)
{
   st_val = 0.0;
   st_dir = 0;
   double prev_upper = 0.0, prev_lower = 0.0, prev_st = 0.0, prev_close = 0.0, atr = 0.0;
   bool was_downtrend = true;

   for(int i = 0; i < bars; i++)
   {
      int shift = bars - i;   // iterate oldest -> newest closed bar
      double h  = iHigh(sym, tf, shift);
      double l  = iLow(sym, tf, shift);
      double c  = iClose(sym, tf, shift);
      double pc = iClose(sym, tf, shift + 1);
      if(h <= 0.0 || l <= 0.0 || c <= 0.0) return;

      double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      atr = (i < period) ? (atr * i + tr) / (i + 1) : (atr * (period - 1) + tr) / period;

      double mid = (h + l) / 2.0;
      double ub  = mid + mult * atr;
      double lb  = mid - mult * atr;

      double upper, lower, st;
      if(i == 0)
      {
         upper = ub; lower = lb; st = ub;
         was_downtrend = true;
      }
      else
      {
         upper = (ub < prev_upper || prev_close > prev_upper) ? ub : prev_upper;
         lower = (lb > prev_lower || prev_close < prev_lower) ? lb : prev_lower;
         if(was_downtrend)
         {
            if(c > upper) { st = lower; was_downtrend = false; }
            else          { st = upper; }
         }
         else
         {
            if(c < lower) { st = upper; was_downtrend = true; }
            else          { st = lower; }
         }
      }

      prev_upper = upper; prev_lower = lower; prev_st = st; prev_close = c;
      if(shift == 1)
      {
         st_val = st;
         st_dir = was_downtrend ? -1 : 1;
      }
   }
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
   macd_h4_handle = iMACD(_Symbol, PERIOD_H4, 12, 26, 9, PRICE_CLOSE);
   atr_h4_handle  = iATR(_Symbol, PERIOD_H4, 14);
   if(macd_h4_handle == INVALID_HANDLE || atr_h4_handle == INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasOpenPosition()) return;

   // 1. SuperTrend direction on H4 (computed natively)
   double st_val;
   int st_dir;
   ComputeSuperTrend(_Symbol, PERIOD_H4, InpStPeriod, InpStMult, InpStBars, st_val, st_dir);
   if(st_dir == 0 || st_val <= 0.0) return;

   // 2. MACD histogram confirmation on H4
   double macd_main = GetBuf(macd_h4_handle, 0, 1);
   double macd_sig  = GetBuf(macd_h4_handle, 1, 1);
   double macd_hist = macd_main - macd_sig;

   double atr_h4  = GetBuf(atr_h4_handle, 0, 1);
   double close1  = iClose(_Symbol, PERIOD_H4, 1);
   if(atr_h4 <= 0.0 || close1 <= 0.0) return;

   // 3. Momentum shift entries: SuperTrend flip + MACD histogram agree (2R target)
   if(st_dir == 1 && macd_hist > 0.0)
   {
      double sl = (st_val < close1) ? st_val : close1 - 1.5 * atr_h4;
      ExecuteBuy(sl, close1 + 2.0 * (close1 - sl));
   }
   else if(st_dir == -1 && macd_hist < 0.0)
   {
      double sl = (st_val > close1) ? st_val : close1 + 1.5 * atr_h4;
      ExecuteSell(sl, close1 - 2.0 * (sl - close1));
   }
}
