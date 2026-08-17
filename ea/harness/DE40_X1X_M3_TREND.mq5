//+------------------------------------------------------------------+
//| DE40_X1X_M3_TREND.mq5                                             |
//| Module 3 candidate: HTF-TREND PULLBACK CONTINUATION (long) + runner|
//| GEN-1 baseline, self-healing campaign.                            |
//|                                                                    |
//| Edge: in an H1 uptrend (EMA20H1 > EMA50H1), a completed M15 pullback|
//| back below the M15 EMA20 that then CLOSES back above EMA20 resumes  |
//| the trend -> LONG. Runner exit (trail from 1R) lets winners run,    |
//| targeting realised RR > 1.0 (distinct from the fade modules).       |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "1.00"
#property strict
#property description "DE40 X1X Module 3 TREND - H1-trend pullback continuation (long) + runner"

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Symbol / Timing ==="
input string InpSymbolOverride = "";
input int    InpServerUTC      = 3;

input group "=== Trend / Pullback ==="
input int    InpEntryStartGMT = 7;
input int    InpEntryEndGMT   = 17;
input double InpSLBufATR     = 0.30;          // stop buffer below pullback extreme

input group "=== Exit (runner) ==="
input bool   InpRunner  = true;               // trail from +1.0R (no fixed 1R TP)
input double InpRunnerCapR = 3.0;             // runner outer TP cap in R

input group "=== GEN-2 Entry Gates ==="
input bool   InpGateShallowPull = false;       // require pullback depth <= InpPullDepMax
input double InpPullDepMax = 0.80;             // max pullback depth (EMA20 - pullLow)/ATR15
input bool   InpGateLowDisp  = false;          // require displacement <= InpDispMax
input double InpDispMax = 0.40;                // max displacement (max 3-bar body / ATR15)

input group "=== Risk / Safety ==="
input double InpLots         = 0.10;
input int    InpMaxSpreadPts = 400;
input int    InpMagic        = 4900;
input int    InpColdStartSec = 30;

string   g_activeSymbol = "";
datetime g_attachTime = 0;
datetime g_lastM15 = 0;

// pullback state
bool     g_inPullback = false;
double   g_pullbackLow = 0;
bool     g_entryDoneForDay = false;

// position state
bool     g_inPosition = false;
int      g_posDir = 0;
double   g_entryPrice = 0, g_sl = 0, g_tp = 0, g_riskPts = 0;
double   g_mfeR = 0, g_maeR = 0;
datetime g_entryTime = 0;
int      g_entryDow = 0, g_entryHour = 0;
string   g_entrySession = "";

int      g_hATR15   = INVALID_HANDLE;
int      g_hEMA20M15= INVALID_HANDLE;
int      g_hEMA200  = INVALID_HANDLE;
int      g_hEMA20H1 = INVALID_HANDLE;
int      g_hEMA50H1 = INVALID_HANDLE;

// telemetry
double   g_f_pullback_depth_atr = 0;   // (EMA20 - pullbackLow)/ATR15
double   g_f_resume_str         = 0;   // (close - EMA20)/ATR15 at resume
double   g_f_price_ema200       = 0;   // (entry - EMA200)/ATR15
double   g_f_atr_pct            = 0;
double   g_f_rel_vol            = 0;
double   g_f_disp               = 0;
int      g_f_h1_bias            = 0;

string DetectDE40Symbol()
{
   if(InpSymbolOverride != "")
      if(SymbolSelect(InpSymbolOverride, true)) return InpSymbolOverride;
   string c[] = {"GER40","GER40.cash","GER40+","DE40","DE40+","DAX40","DAX","Germany40","DEU40","DEU40.cash","GER40m","GER40fs","DAX.fs","DE40fs"};
   for(int i=0;i<ArraySize(c);i++) if(SymbolSelect(c[i],true)) if(SymbolInfoDouble(c[i],SYMBOL_BID)>0) return c[i];
   string cur=_Symbol; StringToUpper(cur);
   if(StringFind(cur,"GER")>=0||StringFind(cur,"DAX")>=0||StringFind(cur,"DE40")>=0||StringFind(cur,"DEU")>=0) return _Symbol;
   return _Symbol;
}

void GmtTime(datetime t, MqlDateTime &dt){ TimeToStruct((datetime)((long)t-(long)InpServerUTC*3600), dt); }
string SessionBucket(int h){ if(h<7)return "Asia"; if(h<8)return "Frankfurt"; if(h<11)return "London"; if(h<13)return "Midday"; if(h<16)return "USOverlap"; return "Late"; }

double GetATR15(){ if(g_hATR15==INVALID_HANDLE) return 0; double b[]; ArraySetAsSeries(b,true); if(CopyBuffer(g_hATR15,0,1,1,b)<1) return 0; return b[0]; }

double EmaVal(int h, int shift){ double b[]; ArraySetAsSeries(b,true); if(CopyBuffer(h,0,shift,1,b)>=1) return b[0]; return 0; }

void ComputeForensics(double entry, double atr15, double ema20, double ema200)
{
   g_f_pullback_depth_atr = (atr15>0) ? (ema20 - g_pullbackLow)/atr15 : 0;
   g_f_resume_str = (atr15>0) ? (entry - ema20)/atr15 : 0;
   g_f_price_ema200 = (atr15>0 && ema200>0) ? (entry - ema200)/atr15 : 0;
   g_f_atr_pct = 0;
   if(g_hATR15!=INVALID_HANDLE){ double ab[]; ArraySetAsSeries(ab,true); int n=CopyBuffer(g_hATR15,0,1,500,ab); if(n>0){ int le=0; for(int i=0;i<n;i++) if(ab[i]<=atr15) le++; g_f_atr_pct=100.0*(double)le/(double)n; } }
   g_f_rel_vol=0; g_f_disp=0;
   MqlRates rb[]; ArraySetAsSeries(rb, true); int nB=CopyRates(g_activeSymbol,PERIOD_M15,0,21,rb);
   if(nB>=21){ double v20=0; for(int i=1;i<=20;i++) v20+=(double)rb[i].tick_volume; if(v20>0) g_f_rel_vol=(double)rb[1].tick_volume*20.0/v20; double mb=0; for(int i=1;i<=3&&i<nB;i++){ double body=MathAbs(rb[i].close-rb[i].open); if(body>mb) mb=body; } if(atr15>0) g_f_disp=mb/atr15; }
   g_f_h1_bias=0; double e20=EmaVal(g_hEMA20H1,1), e50=EmaVal(g_hEMA50H1,1); if(e20>0&&e50>0){ if(e20>e50) g_f_h1_bias=1; else if(e20<e50) g_f_h1_bias=-1; }
}

void TryEntry(double atr15, double ema200)
{
   if(g_inPosition) return;
   double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
   if(entry<=0) return;
   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spread>InpMaxSpreadPts) return;
   if(g_pullbackLow<=0) return;
   double sl = NormalizeDouble(g_pullbackLow - InpSLBufATR*atr15, _Digits);
   double risk = entry - sl; if(risk<=0) return;
   double riskPts = risk/_Point;
   double tp = NormalizeDouble(entry + risk*InpRunnerCapR, _Digits);

   double ema20 = EmaVal(g_hEMA20M15,1);
   ComputeForensics(entry, atr15, ema20, ema200);

   double vstep=SymbolInfoDouble(g_activeSymbol,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(g_activeSymbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(g_activeSymbol,SYMBOL_VOLUME_MAX);
   double lots=InpLots; if(vstep>0) lots=MathFloor(lots/vstep)*vstep; if(lots<vmin) lots=vmin; if(lots>vmax) lots=vmax;
   if(!trade.Buy(lots,g_activeSymbol,entry,sl,tp,"TREND_PULLBACK_LONG")) { Print("M3 order failed ",GetLastError()); return; }
   double fill=trade.ResultPrice();
   g_inPosition=true; g_posDir=+1; g_entryPrice=(fill>0)?fill:entry; g_sl=sl; g_tp=tp; g_riskPts=riskPts; g_mfeR=0; g_maeR=0; g_entryTime=TimeCurrent();
   MqlDateTime dt; GmtTime(g_entryTime,dt); g_entryDow=dt.day_of_week; g_entryHour=dt.hour; g_entrySession=SessionBucket(dt.hour);
   Print("TREND_PULLBACK_LONG | entry=",DoubleToString(g_entryPrice,_Digits)," sl=",DoubleToString(sl,_Digits)," tp=",DoubleToString(tp,_Digits)," pullLow=",DoubleToString(g_pullbackLow,_Digits)," h1bias=",g_f_h1_bias);
}

void EvaluateNewBar()
{
   double c1=iClose(g_activeSymbol,PERIOD_M15,1), l1=iLow(g_activeSymbol,PERIOD_M15,1), h1v=iHigh(g_activeSymbol,PERIOD_M15,1);
   if(c1<=0) return;
   double atr15=GetATR15(); if(atr15<=0) return;
   double ema20=EmaVal(g_hEMA20M15,1); if(ema20<=0) return;
   double ema200=EmaVal(g_hEMA200,1);

   // H1 trend must be up
   if(g_f_h1_bias != 1)
   { double e20=EmaVal(g_hEMA20H1,1), e50=EmaVal(g_hEMA50H1,1); if(!(e20>0&&e50>0&&e20>e50)) return; }

   if(g_entryDoneForDay) return;

   if(!g_inPullback)
   {
      if(c1 < ema20) { g_inPullback=true; g_pullbackLow=l1; }
      return;
   }
   if(l1 < g_pullbackLow) g_pullbackLow = l1;
   if(c1 > ema20)   // pullback reclaimed -> resume -> long
   {
      g_inPullback=false;
      // evidence gates (baseline-derived)
      double pd = (atr15>0) ? (ema20 - g_pullbackLow)/atr15 : 99.0;
      if(InpGateShallowPull && pd > InpPullDepMax)
      { g_entryDoneForDay=true; Print("M3 GateShallowPull blocked pd=",DoubleToString(pd,3)); return; }
      if(InpGateLowDisp)
      {
         MqlRates rb[]; double mb=0; int nB=CopyRates(g_activeSymbol,PERIOD_M15,1,3,rb);
         for(int i=0;i<nB;i++){ double body=MathAbs(rb[i].close-rb[i].open); if(body>mb) mb=body; }
         double disp = (atr15>0)?mb/atr15:99.0;
         if(disp > InpDispMax)
         { g_entryDoneForDay=true; Print("M3 GateLowDisp blocked disp=",DoubleToString(disp,3)); return; }
      }
      g_entryDoneForDay=true;
      MqlDateTime dt; GmtTime(iTime(g_activeSymbol,PERIOD_M15,1),dt);
      if(dt.hour>=InpEntryStartGMT && dt.hour<InpEntryEndGMT) TryEntry(atr15, ema200);
   }
}

bool FindExitDeal(double &price, datetime &time)
{
   price=0; time=0; if(!HistorySelect(g_entryTime,TimeCurrent()+120)) return false;
   int n=HistoryDealsTotal();
   for(int i=n-1;i>=0;i--){ ulong t=HistoryDealGetTicket(i); if(t==0) continue; if(HistoryDealGetString(t,DEAL_SYMBOL)!=g_activeSymbol) continue; if(HistoryDealGetInteger(t,DEAL_MAGIC)!=(long)InpMagic) continue; ENUM_DEAL_ENTRY e=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(t,DEAL_ENTRY); if(e==DEAL_ENTRY_OUT||e==DEAL_ENTRY_INOUT){ price=HistoryDealGetDouble(t,DEAL_PRICE); time=(datetime)HistoryDealGetInteger(t,DEAL_TIME); return true; } }
   return false;
}

void LogTradeClose(double exitPrice, datetime exitTime)
{
   if(g_entryPrice<=0||g_riskPts<=0) return;
   double R=(exitPrice-g_entryPrice)/_Point/g_riskPts;
   string fn=StringFormat("DE40X1_TRADES_%d.csv",InpMagic);
   int h=FileOpen(fn,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,','); bool need=false;
   if(h==INVALID_HANDLE){ h=FileOpen(fn,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,','); need=true; } else { FileSeek(h,0,SEEK_END); need=(FileSize(h)<=0); }
   if(h==INVALID_HANDLE) return;
   if(need) FileWrite(h,"time_open","time_close","side","entry","sl","tp","exit_price","R","MFE_R","MAE_R","module","gmt_hour","weekday","session_bucket","pullback_depth_atr","resume_str","f_price_ema200","f_atr_pct","f_rel_vol","f_disp","f_h1_bias");
   FileWrite(h,(long)g_entryTime,(long)exitTime,"BUY",DoubleToString(g_entryPrice,_Digits),DoubleToString(g_sl,_Digits),DoubleToString(g_tp,_Digits),DoubleToString(exitPrice,_Digits),DoubleToString(R,4),DoubleToString(g_mfeR,4),DoubleToString(g_maeR,4),"TREND",g_entryHour,g_entryDow,g_entrySession,DoubleToString(g_f_pullback_depth_atr,4),DoubleToString(g_f_resume_str,4),DoubleToString(g_f_price_ema200,4),DoubleToString(g_f_atr_pct,4),DoubleToString(g_f_rel_vol,4),DoubleToString(g_f_disp,4),g_f_h1_bias);
   FileClose(h);
   Print("M3 trade logged | R=",DoubleToString(R,3)," MFE=",DoubleToString(g_mfeR,3)," MAE=",DoubleToString(g_maeR,3));
}

void ResetPosState(){ g_inPosition=false; g_posDir=0; g_entryPrice=0; g_sl=0; g_tp=0; g_riskPts=0; g_mfeR=0; g_maeR=0; g_entryTime=0; g_entryDow=0; g_entryHour=0; g_entrySession=""; g_f_pullback_depth_atr=0; g_f_resume_str=0; g_f_price_ema200=0; g_f_atr_pct=0; g_f_rel_vol=0; g_f_disp=0; g_f_h1_bias=0; }

void ManagePosition()
{
   if(!g_inPosition) return;
   ulong tk=0; bool found=false;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i); if(t==0) continue; if(PositionGetString(POSITION_SYMBOL)!=g_activeSymbol) continue; if(PositionGetInteger(POSITION_MAGIC)==(long)InpMagic){ found=true; tk=t; break; } }
   if(!found){ double ep=0; datetime et=0; if(!FindExitDeal(ep,et)) return; LogTradeClose(ep,et); ResetPosState(); return; }
   double cur=SymbolInfoDouble(g_activeSymbol,SYMBOL_BID); if(cur<=0||g_riskPts<=0) return;
   double r=(cur-g_entryPrice)/_Point/g_riskPts;
   if(r>g_mfeR) g_mfeR=r; if(r<g_maeR) g_maeR=r;
   if(InpRunner && r>=1.0 && g_posDir==+1){ if(PositionSelectByTicket(tk)){ double tr=NormalizeDouble(g_entryPrice+(g_mfeR-1.0)*g_riskPts*_Point,_Digits); double cs=PositionGetDouble(POSITION_SL); if(tr>cs && trade.PositionModify(tk,tr,PositionGetDouble(POSITION_TP))) Print("M3 runner trail SL=",DoubleToString(tr,_Digits)); } }
}

int OnInit()
{
   g_activeSymbol=DetectDE40Symbol(); if(!SymbolSelect(g_activeSymbol,true)) return INIT_FAILED;
   g_hATR15=iATR(g_activeSymbol,PERIOD_M15,14);
   g_hEMA20M15=iMA(g_activeSymbol,PERIOD_M15,20,0,MODE_EMA,PRICE_CLOSE);
   g_hEMA200=iMA(g_activeSymbol,PERIOD_M15,200,0,MODE_EMA,PRICE_CLOSE);
   g_hEMA20H1=iMA(g_activeSymbol,PERIOD_H1,20,0,MODE_EMA,PRICE_CLOSE);
   g_hEMA50H1=iMA(g_activeSymbol,PERIOD_H1,50,0,MODE_EMA,PRICE_CLOSE);
   if(g_hATR15==INVALID_HANDLE||g_hEMA20M15==INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(30);
   g_attachTime=TimeCurrent(); g_lastM15=0; g_inPullback=false; g_pullbackLow=0; g_entryDoneForDay=false; ResetPosState();
   Print("=== DE40 X1X Module 3 TREND v1.00 (magic ",InpMagic,") ===");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int r){ if(g_hATR15!=INVALID_HANDLE)IndicatorRelease(g_hATR15); if(g_hEMA20M15!=INVALID_HANDLE)IndicatorRelease(g_hEMA20M15); if(g_hEMA200!=INVALID_HANDLE)IndicatorRelease(g_hEMA200); if(g_hEMA20H1!=INVALID_HANDLE)IndicatorRelease(g_hEMA20H1); if(g_hEMA50H1!=INVALID_HANDLE)IndicatorRelease(g_hEMA50H1); }

void OnTick()
{
   ManagePosition(); if(g_inPosition) return;
   if(TimeCurrent()-g_attachTime < InpColdStartSec) return;
   datetime m15=iTime(g_activeSymbol,PERIOD_M15,1); if(m15<=0||m15==g_lastM15) return; g_lastM15=m15;
   MqlDateTime dt; GmtTime(TimeCurrent(),dt); if(dt.day_of_week==0||dt.day_of_week==6) return;
   // reset day state
   static datetime d1=0; datetime d=iTime(g_activeSymbol,PERIOD_D1,0); if(d!=d1){ d1=d; g_inPullback=false; g_pullbackLow=0; g_entryDoneForDay=false; }
   EvaluateNewBar();
}
//+------------------------------------------------------------------+