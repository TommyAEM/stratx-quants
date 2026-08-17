//+------------------------------------------------------------------+
//| Module 12: DE40 Donchian Trend Ride (H1 Breakout)                |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "1.00"
#include <Trade/Trade.mqh>

input int    InpDonchianPeriod = 20;
input double InpAdxMin         = 25.0;
input double InpRiskPercent    = 0.5;
input long   InpMagic          = 260112;
input string InpComment        = "M12_DonchianH1";

CTrade   trade;
int      adx_h1_handle = INVALID_HANDLE;
datetime g_last_bar_time = 0;

bool IsNewBar()
{
   datetime cur_bar_time = iTime(_Symbol, _Period, 0);
   if(cur_bar_time == g_last_bar_time) return false;
   g_last_bar_time = cur_bar_time;
   return true;
}

double GetH1ADX(int shift)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(adx_h1_handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
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
   adx_h1_handle = iADX(_Symbol, PERIOD_H1, 14);
   if(adx_h1_handle == INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasOpenPosition()) return;

   // 1. Trend strength gate: ADX must confirm a real trend
   double adx = GetH1ADX(1);
   if(adx < InpAdxMin) return;

   // 2. Donchian channel over closed H1 bars
   int hi_idx = iHighest(_Symbol, PERIOD_H1, MODE_HIGH, InpDonchianPeriod, 1);
   int lo_idx = iLowest(_Symbol, PERIOD_H1, MODE_LOW, InpDonchianPeriod, 1);
   if(hi_idx < 0 || lo_idx < 0) return;
   double dc_high = iHigh(_Symbol, PERIOD_H1, hi_idx);
   double dc_low  = iLow(_Symbol, PERIOD_H1, lo_idx);
   if(dc_high <= dc_low) return;

   // 3. Breakout entries on the last closed H1 bar (2:1 RR, SL at opposite band)
   double close1 = iClose(_Symbol, PERIOD_H1, 1);
   if(close1 > dc_high)
   {
      double sl = dc_low;
      double tp = close1 + 2.0 * (close1 - sl);
      ExecuteBuy(sl, tp);
   }
   else if(close1 < dc_low)
   {
      double sl = dc_high;
      double tp = close1 - 2.0 * (sl - close1);
      ExecuteSell(sl, tp);
   }
}
