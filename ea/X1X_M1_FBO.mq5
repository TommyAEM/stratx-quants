//+------------------------------------------------------------------+
//| X1X_M1_FBO.mq5 - DE40 False Breakout Reversal (X1X Flagship)      |
//| Causal Mutation: Regime Filter (Session & Volatility Gates)       |
//+------------------------------------------------------------------+
#property copyright "StratX Institutional Quant Desk"
#property version   "2.20-DE40"
#property strict
#include <Trade/Trade.mqh>

CTrade trade;

//=== BLOCK 1: INPUTS & GLOBAL HANDLES ===
input double InpRiskPercent        = 1.0;    // 1.0% equity risk per trade
input long   InpMagic              = 260101; // Magic number
input string InpComment            = "X1X_M1_FBO";

// Core Geometry
input double InpMinBreakATR        = 0.8;    // Min breakout beyond level (ATR)
input double InpMaxBreakATR        = 2.5;    // Max breakout (beyond = real breakout)
input int    InpMaxBarsOutside     = 8;      // Max bars outside before abort
input double InpDispBodyATR        = 0.8;    // Displacement candle body min (ATR)
input double InpFillFraction       = 0.5;    // Equilibrium retrace depth into zone (50%)

// Sessions (Frankfurt / London European Core Hours GMT)
input int    InpAsiaStartGMT       = 0;      // Asian session start (GMT)
input int    InpAsiaEndGMT         = 7;      // Asian session end (GMT)
input int    InpTradeStartGMT      = 7;      // Trading start (Frankfurt Open 07:00 GMT)
input int    InpTradeEndGMT        = 16;     // Trading end (16:30 GMT)
input int    InpTradeEndMin        = 30;

// Regime Filter (Session & Volatility Gates)
input int    InpRegimeSessionStartGMT = 8;        // Regime session start (GMT) - high volatility window
input int    InpRegimeSessionEndGMT   = 12;       // Regime session end (GMT)
input double InpMinATRVolatility      = 0.0;      // Min ATR for volatility gate (points)
input double InpMaxATRVolatility      = 999.9;    // Max ATR for volatility gate (points)

// FBL Exit Management (Flagship Pattern)
input bool   InpEnablePartialClose = true;   // 50% partial close at 1.0R
input double InpPartialTargetR       = 1.0;    // TP1 level (1.0R)
input bool   InpMoveRunnerToBE       = true;   // Move runner SL to BE after TP1
input double InpBECostBuffer         = 0.05;   // BE cost buffer
input bool   InpEnableATRTrail       = true;   // Enable ATR trailing on runner
input double InpATRTrailMultiplier   = 1.5;    // 1.5x ATR trailing distance
input double InpRunnerMaxR           = 3.0;    // Runner max target (3.0R)

int      atr_handle = INVALID_HANDLE;
datetime last_bar_time = 0;

// Setup State Machine
#define ST_IDLE     0
#define ST_BREAKOUT 1
#define ST_FAILED   2
#define ST_ARMED    3

int    fbo_state      = ST_IDLE;
int    fbo_dir        = 0; // +1 = bull fakeout (buy), -1 = bear fakeout (sell)
double fbo_level      = 0.0;
double fbo_extreme    = 0.0;
int    fbo_bars_out   = 0;
double fbo_zone_top   = 0.0;
double fbo_zone_bot   = 0.0;

// Session Level Storage
double asia_high = 0.0;
double asia_low  = 0.0;
datetime last_asia_calc = 0;

// Position Tracking
bool   in_trade = false;
ulong  active_ticket = 0;
double entry_price = 0.0;
double initial_sl = 0.0;
double initial_risk = 0.0;
bool   tp1_taken = false;

//=== BLOCK 2: EXECUTION GUARDS ===
bool IsNewBar()
{
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == last_bar_time) return false;
   last_bar_time = cur;
   return true;
}

void GetHourMin(int &hour, int &minute)
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   hour = dt.hour;
   minute = dt.min;
}

bool InTradingSession()
{
   int h, m;
   GetHourMin(h, m);
   int now_m = h * 60 + m;
   int start_m = InpTradeStartGMT * 60;
   int end_m = InpTradeEndGMT * 60 + InpTradeEndMin;
   return (now_m >= start_m && now_m <= end_m);
}

double GetATR(int shift)
{
   double buf[1];
   if(CopyBuffer(atr_handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

void UpdateAsiaLevels()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime day_start = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   if(day_start == last_asia_calc && asia_high > 0.0) return;

   int start_bar = iBarShift(_Symbol, PERIOD_M15, day_start + InpAsiaStartGMT * 3600);
   int end_bar   = iBarShift(_Symbol, PERIOD_M15, day_start + InpAsiaEndGMT * 3600);
   if(start_bar <= 0 || end_bar <= 0 || start_bar <= end_bar) return;

   asia_high = iHigh(_Symbol, PERIOD_M15, end_bar);
   asia_low  = iLow(_Symbol, PERIOD_M15, end_bar);
   for(int b = end_bar; b <= start_bar; b++)
   {
      double h = iHigh(_Symbol, PERIOD_M15, b);
      double l = iLow(_Symbol, PERIOD_M15, b);
      if(h > asia_high) asia_high = h;
      if(l < asia_low && l > 0.0) asia_low = l;
   }
   last_asia_calc = day_start;
}

//=== BLOCK 3: REGIME & CONFLUENCE GATES (MUTATION) ===
bool IsRegimeSession()
{
   int h, m;
   GetHourMin(h, m);
   int now_m = h * 60 + m;
   int start_m = InpRegimeSessionStartGMT * 60;
   int end_m = InpRegimeSessionEndGMT * 60;
   return (now_m >= start_m && now_m <= end_m);
}

bool IsVolatilityGate(double atr)
{
   // atr is in instrument points, compare directly with thresholds
   if(atr < InpMinATRVolatility) return false;
   if(atr > InpMaxATRVolatility) return false;
   return true;
}

//=== BLOCK 5: RISK & SIZING ===
double CalcLots(double sl_dist)
{
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_val <= 0.0 || tick_sz <= 0.0 || sl_dist <= 0.0) return 0.01;
   double risk_amt = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
   double lots     = NormalizeDouble(risk_amt / ((sl_dist / tick_sz) * tick_val), 2);
   double min_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   return MathMax(min_lot, MathMin(max_lot, lots));
}

//=== BLOCK 6: ORDER DISPATCH & FBL EXIT MANAGEMENT ===
void ManageFBLExit()
{
   if(!PositionSelectByTicket(active_ticket))
   {
      in_trade = false;
      active_ticket = 0;
      return;
   }

   double cur_price = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pos_vol = PositionGetDouble(POSITION_VOLUME);
   double pos_sl  = PositionGetDouble(POSITION_SL);
   double atr     = GetATR(1);

   if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
   {
      double gain_r = (initial_risk > 0.0) ? (cur_price - entry_price) / initial_risk : 0.0;
      // Partial close at 1.0R
      if(!tp1_taken && InpEnablePartialClose && gain_r >= InpPartialTargetR && pos_vol >= 0.02)
      {
         double close_vol = NormalizeDouble(pos_vol * 0.5, 2);
         if(trade.PositionClosePartial(active_ticket, close_vol))
         {
            tp1_taken = true;
            if(InpMoveRunnerToBE)
            {
               double be_sl = NormalizeDouble(entry_price + initial_risk * InpBECostBuffer, _Digits);
               trade.PositionModify(active_ticket, be_sl, NormalizeDouble(entry_price + initial_risk * InpRunnerMaxR, _Digits));
            }
         }
      }
      // ATR Trail on Runner
      if(tp1_taken && InpEnableATRTrail && atr > 0.0)
      {
         double trail_sl = NormalizeDouble(cur_price - InpATRTrailMultiplier * atr, _Digits);
         if(trail_sl > pos_sl) trade.PositionModify(active_ticket, trail_sl, PositionGetDouble(POSITION_TP));
      }
   }
   else
   {
      double gain_r = (initial_risk > 0.0) ? (entry_price - cur_price) / initial_risk : 0.0;
      if(!tp1_taken && InpEnablePartialClose && gain_r >= InpPartialTargetR && pos_vol >= 0.02)
      {
         double close_vol = NormalizeDouble(pos_vol * 0.5, 2);
         if(trade.PositionClosePartial(active_ticket, close_vol))
         {
            tp1_taken = true;
            if(InpMoveRunnerToBE)
            {
               double be_sl = NormalizeDouble(entry_price - initial_risk * InpBECostBuffer, _Digits);
               trade.PositionModify(active_ticket, be_sl, NormalizeDouble(entry_price - initial_risk * InpRunnerMaxR, _Digits));
            }
         }
      }
      if(tp1_taken && InpEnableATRTrail && atr > 0.0)
      {
         double trail_sl = NormalizeDouble(cur_price + InpATRTrailMultiplier * atr, _Digits);
         if(pos_sl == 0.0 || trail_sl < pos_sl) trade.PositionModify(active_ticket, trail_sl, PositionGetDouble(POSITION_TP));
      }
   }
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
   
   if(in_trade)
   {
      ManageFBLExit();
      return;
   }

   UpdateAsiaLevels();
   if(asia_high <= 0.0 || asia_low <= 0.0) return;
   if(!InTradingSession()) return;

   double atr = GetATR(1);
   if(atr <= 0.0) return;

   //=== BLOCK 3: REGIME & CONFLUENCE GATES ===
   if(!IsRegimeSession()) return;
   if(!IsVolatilityGate(atr)) return;

   double high1 = iHigh(_Symbol, _Period, 1);
   double low1  = iLow(_Symbol, _Period, 1);
   double close1= iClose(_Symbol, _Period, 1);
   double open1 = iOpen(_Symbol, _Period, 1);

   // === BLOCK 4: ALPHA TRIGGER & FBO REVERSAL ===
   // Detect Bullish Fakeout of Asian Low (Sweep Low -> Close back inside)
   if(fbo_state == ST_IDLE)
   {
      if(low1 < asia_low && (asia_low - low1) >= InpMinBreakATR * atr && (asia_low - low1) <= InpMaxBreakATR * atr)
      {
         fbo_state    = ST_BREAKOUT;
         fbo_dir      = 1;
         fbo_level    = asia_low;
         fbo_extreme  = low1;
         fbo_bars_out = 1;
      }
      else if(high1 > asia_high && (high1 - asia_high) >= InpMinBreakATR * atr && (high1 - asia_high) <= InpMaxBreakATR * atr)
      {
         fbo_state    = ST_BREAKOUT;
         fbo_dir      = -1;
         fbo_level    = asia_high;
         fbo_extreme  = high1;
         fbo_bars_out = 1;
      }
   }
   else if(fbo_state == ST_BREAKOUT)
   {
      fbo_bars_out++;
      if(fbo_bars_out > InpMaxBarsOutside) { fbo_state = ST_IDLE; return; }

      if(fbo_dir == 1) // Bullish Fakeout
      {
         if(low1 < fbo_extreme) fbo_extreme = low1;
         // Displacement candle back above Asian Low
         if(close1 > fbo_level && (close1 - open1) >= InpDispBodyATR * atr)
         {
            fbo_state    = ST_ARMED;
            fbo_zone_bot = fbo_extreme;
            fbo_zone_top = close1;
         }
      }
      else if(fbo_dir == -1) // Bearish Fakeout
      {
         if(high1 > fbo_extreme) fbo_extreme = high1;
         // Displacement candle back below Asian High
         if(close1 < fbo_level && (open1 - close1) >= InpDispBodyATR * atr)
         {
            fbo_state    = ST_ARMED;
            fbo_zone_top = fbo_extreme;
            fbo_zone_bot = close1;
         }
      }
   }
   else if(fbo_state == ST_ARMED)
   {
      // 50% Equilibrium Retrace Mitigation Entry
      if(fbo_dir == 1 && low1 <= (fbo_zone_bot + (fbo_zone_top - fbo_zone_bot) * InpFillFraction))
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = NormalizeDouble(fbo_extreme - 0.5 * atr, _Digits);
         initial_risk = ask - sl;
         if(initial_risk > 0.0)
         {
            double tp = NormalizeDouble(ask + initial_risk * InpRunnerMaxR, _Digits);
            if(trade.Buy(CalcLots(initial_risk), _Symbol, 0.0, sl, tp, InpComment))
            {
               in_trade = true;
               active_ticket = trade.ResultOrder();
               entry_price = ask;
               initial_sl = sl;
               tp1_taken = false;
               fbo_state = ST_IDLE;
            }
         }
      }
      else if(fbo_dir == -1 && high1 >= (fbo_zone_top - (fbo_zone_top - fbo_zone_bot) * InpFillFraction))
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = NormalizeDouble(fbo_extreme + 0.5 * atr, _Digits);
         initial_risk = sl - bid;
         if(initial_risk > 0.0)
         {
            double tp = NormalizeDouble(bid - initial_risk * InpRunnerMaxR, _Digits);
            if(trade.Sell(CalcLots(initial_risk), _Symbol, 0.0, sl, tp, InpComment))
            {
               in_trade = true;
               active_ticket = trade.ResultOrder();
               entry_price = bid;
               initial_sl = sl;
               tp1_taken = false;
               fbo_state = ST_IDLE;
            }
         }
      }
   }
}