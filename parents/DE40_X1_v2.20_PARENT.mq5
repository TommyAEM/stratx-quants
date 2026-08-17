//+------------------------------------------------------------------+
//| DE40_X1.mq5  (DE40 X1 — DAX Failed Breakout)                     |
//| Ported from US30 X1 v5.11 (DJ30_M4_FailedBO_SH5)                 |
//| Adapted for German DAX/DE40 index with:                          |
//|   - Configurable symbol detection (GER40/DE40/DAX40/etc)         |
//|   - Frankfurt/Xetra/London session timing                        |
//|   - FDAX confluence data support (optional)                      |
//|   - DE40-calibrated ATR/spread/volatility thresholds             |
//|   - Individual module testing via LevelMask presets              |
//|   - Pre-London/Frankfurt range support                           |
//| v1.00: Initial DE40 port from US30 X1 SH2 final                  |
//| v2.00: Eight-module architecture                                 |
//|   - Modules A-F: FBO state machine on 6 structural levels        |
//|     (A=5mOR B=10mOR C=15mOR D=Asia E=PreLdn F=PDH/PDL)           |
//|   - Module G: Goldilocks EMA pullback continuation               |
//|     (method from USDCHF GLK research: stacked EMAs, ATR-banded   |
//|      separation, slope persistence, pullback + rejection)        |
//|   - Module H: genuine session-VWAP / structure pullback cont.    |
//|   - InpModuleMask selects modules (0 = legacy LevelMask mode)    |
//|   - Per-module magic: FBO=InpMagic, GLK=+1, VWAP=+2              |
//+------------------------------------------------------------------+
#property copyright "StratX Research"
#property version   "2.20"
#property strict
#property description "DE40 X1 — Failed Breakout strategy for German DAX index"
#property description "Ported from US30 X1 v5.11 with DE40-specific calibration"

#include <Trade\Trade.mqh>
CTrade trade;

// ---- Symbol detection ---------------------------------------------------
input group "=== Symbol Configuration ==="
input string InpSymbolOverride = "";     // Override symbol (empty=auto-detect)
input int    InpServerUTC      = 2;      // Server UTC offset (Vantage=2, PUPrime=3)

// ---- Module architecture --------------------------------------------------
input group "=== Module Architecture ==="
input int    InpModuleMask     = 0;      // 0=legacy LevelMask mode; else bits 0..5=FBO A-F, 6=Goldilocks, 7=VWAP

// ---- risk level selector ------------------------------------------------
enum ENUM_RISK_LEVEL {
   RISK_OPTIMIZED = 0,  // Optimized - 0.5% per trade
   RISK_MEDIUM    = 1,  // Medium - 1.25% per trade
   RISK_HIGH      = 2,  // High - 2.50% per trade
   RISK_MAX       = 3   // Max - 5.00% per trade
};

//=== CORE GEOMETRY (FBO state machine — unchanged from US30) ===
input group "=== FBO Core Geometry ==="
input double InpMinBreakATR    = 1.0;    // min breakout beyond level (ATR)
input double InpMaxBreakATR    = 1.5;    // max breakout (beyond = real BO)
input int    InpMaxBarsOutside = 8;      // max bars outside before abort
input double InpDispBodyATR    = 1.0;    // displacement body min (ATR)
input int    InpMaxBarsToDisp  = 12;     // max bars for displacement
input double InpMinGapATR      = 0.15;   // min FVG gap (ATR)
input int    InpMaxBarsToIfvg  = 20;     // max bars for IFVG after fail
input int    InpMaxRetraceBars = 20;     // max bars for retrace into zone
input double InpMaxIfvgDistATR = 4.0;    // max IFVG distance from level
input int    InpEntryMode      = 4;      // 0=touch,1=mid,2=fill,3=confirm,4=struct
input double InpFillFraction   = 0.5;
input int    InpStructShiftBars= 5;
input int    InpIfvgScanBars   = 30;
input bool   InpUseIFVG        = false;  // false=bypass IFVG, use disp leg as zone
input double InpRetracePct     = 0.5;    // retrace depth into disp leg

//=== LEVEL SOURCES (bitmask) ===
input group "=== Level Sources ==="
input int    InpLevelMask      = 40;     // bit0=5mOR,1=10mOR,2=15mOR,3=Asia,4=PreLdn,5=PDH/PDL,6=EqHL
input bool   InpFboAllowShort  = true;   // allow FBO short entries (false=longs only)
input int    InpORAnchorGMT    = 8;      // DE40: Xetra cash open (08:00 GMT winter)
input int    InpORAnchorMin    = 0;
input int    InpAsiaStartGMT   = 0;
input int    InpAsiaEndGMT     = 7;
input int    InpPreLdnStartGMT = 6;      // DE40: Frankfurt pre-market start
input int    InpPreLdnEndGMT   = 8;      // DE40: Xetra open
input double InpEqTolATR      = 0.3;
input int    InpEqSwingLb      = 5;
input int    InpEqScanBars     = 120;

//=== SESSIONS (DE40-specific) ===
input group "=== Trading Sessions ==="
input int    InpSessionMask    = 7;      // bit0=Frankfurt,1=London,2=XetraCash,3=USOverlap
input int    InpFrankStartGMT  = 7;
input int    InpFrankEndGMT    = 8;
input int    InpLdnStartGMT    = 8;
input int    InpLdnEndGMT      = 11;
input int    InpXetraStartGMT  = 8;
input int    InpXetraEndGMT    = 10;
input int    InpUSOvlpStartGMT = 13;
input int    InpUSOvlpStartMin = 30;
input int    InpUSOvlpEndGMT   = 16;
input int    InpUSOvlpEndMin   = 0;

//=== TRADE MANAGEMENT ===
input group "=== Trade Management ==="
input int    InpMaxTradesDay   = 2;
input int    InpMagic          = 446404093;
input ENUM_RISK_LEVEL InpRiskLevel = RISK_MEDIUM;
input int    InpSLMode         = 0;      // 0=boExtreme,1=fixedATR,2=zone
input double InpSL_BufferATR   = 0.3;
input double InpSL_ATR         = 1.5;
input int    InpTPMode         = 3;      // 3=fixedRR
input double InpTP_RR          = 1.0;
input int    InpTimeStopMin    = 0;
input double InpMaxSpreadPts   = 500;    // DE40: tighter than US30 (1000)

//=== FBL EXIT MANAGEMENT ===
input group "=== FBL Exit Management ==="
input bool   InpEnablePartialClose = true;
input int    InpPartialPercent     = 50;
input double InpPartialTargetR     = 0.6;
input bool   InpMoveRunnerToBE     = true;
input double InpBECostBuffer       = 0.05;
input bool   InpEnableATRTrail     = true;
input int    InpATRTrailPeriod     = 14;
input double InpATRTrailMultiplier = 1.5;
input ENUM_TIMEFRAMES InpTrailTimeframe = PERIOD_H1;
input double InpTrailActivationR   = 0.0;
input double InpRunnerMaxR         = 3.0;

//=== FILTERS (DE40-calibrated) ===
input group "=== Volatility Filters ==="
input int    InpATRPeriod      = 14;
input double InpMinATR         = 5.0;    // DE40: higher floor (US30=2.0)
input double InpMaxATR         = 800.0;  // DE40: higher ceiling (US30=500)

//=== FDAX CONFLUENCE SCORING ===
input group "=== FDAX Confluence ==="
input int    InpConfMode       = 0;      // 0=off (default until FDAX data available)
input string InpConfDataFile   = "FDAX_M15_FEATURES.csv";
input double InpMinConfScore   = 4.0;
input double InpW_VwapDist     = 3.0;
input double InpW_CumSlope     = 2.0;
input double InpW_VolRatio     = 1.0;
input double InpW_DeltaZ       = 1.0;
input double InpW_Setup        = 1.0;
input double InpVolRatioThresh = 1.2;
input double InpDeltaZThresh   = 0.0;
input int    InpMinBarsToDisp  = 7;
input int    InpMinRetraceBars = 3;
input double InpVwapSoftThresh = 0.0;
input int    InpVwapGateDir    = 0;

//=== MODULE G: GOLDILOCKS EMA PULLBACK CONTINUATION ===
input group "=== Module G: Goldilocks Pullback ==="
input int    InpGlkFast        = 9;      // Fast EMA period
input int    InpGlkMed         = 21;     // Medium EMA period
input int    InpGlkSlow        = 50;     // Slow EMA period
input ENUM_TIMEFRAMES InpGlkTimeframe = PERIOD_M15; // GLK evaluation timeframe
input int    InpGlkATRPeriod   = 14;     // GLK ATR period (on GLK timeframe)
input int    InpGlkPersist     = 3;      // bars of stacked EMA alignment required
input double InpGlkSepMinATR   = 0.15;   // min fast-med / med-slow separation (ATR)
input double InpGlkSepMaxATR   = 2.5;    // max separation (overextension veto)
input int    InpGlkSlopeLb     = 5;      // separation-slope lookback (bars)
input double InpGlkSlopeMin    = 0.0;    // min sep change over lookback (ATR units)
input double InpGlkMinPullATR  = 0.3;    // min pullback depth (ATR)
input int    InpGlkMaxPullBars = 12;     // max bars allowed for pullback
input double InpGlkInvalATR    = 0.8;    // close beyond slow EMA +/- this*ATR invalidates
input double InpGlkSLBufATR    = 0.3;    // SL buffer beyond pullback extreme (ATR)
input double InpGlkMaxSLATR    = 4.5;    // max stop distance (ATR)
input double InpGlkTP_RR       = 1.2;    // fixed RR when FBL exit disabled
input int    InpGlkStartGMT    = 8;      // entries from this GMT hour
input int    InpGlkEndGMT      = 16;     // entries until this GMT hour
input bool   InpGlkAllowShort  = true;   // allow GLK short setups

//=== MODULE H: SESSION VWAP / STRUCTURE CONTINUATION ===
input group "=== Module H: VWAP Continuation ==="
input int    InpVwapStartGMT   = 8;      // session VWAP anchor hour (Xetra open), GMT
input int    InpVwapEndGMT     = 16;     // entries only before this GMT hour
input int    InpVwapStructLb   = 12;     // local structure lookback (chart bars)
input int    InpVwapSlopeBars  = 30;     // M1 bars for VWAP slope comparison
input double InpVwapBandATR    = 0.5;    // pullback touch band around VWAP (ATR)
input double InpVwapBreakATR   = 1.0;    // close beyond VWAP +/- this*ATR invalidates
input double InpVwapMaxPullATR = 3.0;    // max pullback depth from breakout (ATR)
input int    InpVwapMaxPullBars= 12;     // max bars allowed for pullback
input double InpVwapSLBufATR   = 0.3;    // SL buffer beyond pullback extreme (ATR)
input double InpVwapMaxSLATR   = 4.5;    // max stop distance (ATR)
input double InpVwapTP_RR      = 1.2;    // fixed RR when FBL exit disabled
input double InpVwapMinRoomR   = 1.5;    // min room to opposing PDH/PDL (stop units)
input bool   InpVwapAllowShort = true;   // allow VWAP short setups

//=== NATIVE ENTRY-QUALITY CONFLUENCE (no external feed required) ===
input group "=== Native Confluence Gate ==="
input int    InpUseNativeConf  = 0;      // 0=off, 1=score, 2=hard gate (all checks)
input bool   InpNcTrendFilter  = true;   // M15 EMA trend filter (no counter-trend)
input int    InpNcTrendPeriod  = 200;    // trend EMA period (chart TF)
input bool   InpNcVwapSide     = true;   // entry side must match session-VWAP side
input bool   InpNcVolSpike     = true;   // trigger bar tick volume >= X * 20-bar avg
input double InpNcVolMult      = 1.3;    // volume spike multiplier
input double InpNcMinScore     = 3.0;    // min score in mode 1 (1 point per check)

//=== NEWS AVOIDANCE ===
input group "=== News Avoidance ==="
input bool   InpNewsAvoid      = true;
input int    InpNewsWindow     = 30;
input int    InpNewsImpact     = 2;
input string InpNewsCurrencies = "EUR";  // DE40: Eurozone news

//=== DASHBOARD ===
input group "=== Dashboard ==="
input bool   InpShowDashboard  = true;
input int    InpDashX          = 20;
input int    InpDashY          = 30;

//=== SAFETY ===
input group "=== Safety ==="
input int    InpStopLossDay    = 2;
input double InpDDCutPct       = 6.0;
input int    InpColdStartSec   = 30;

//+------------------------------------------------------------------+
#define ST_IDLE     0
#define ST_BREAKOUT 1
#define ST_FAILED   2
#define ST_ARMED    3
#define MAX_LEVELS  7
#define GC_MAX_ROWS 70000

//=== FDAX DATA ARRAYS ===
datetime g_gcTime[];
double   g_gcClose[], g_gcDelta[], g_gcCumDelta[], g_gcVwap[];
double   g_gcImbalance[], g_gcVolume[], g_gcVolSpike[], g_gcAbsorption[], g_gcPdDiv[];
int      g_gcRows = 0;

struct FBOSetup
{
   int    state;
   int    dir;
   double level;
   double rangeHigh, rangeLow;
   double boExtreme;
   int    barsOutside;
   int    failBar;
   bool   dispSeen;
   double zTop, zBottom;
   int    armBar;
   int    levelType;
   int    barsToDisp;
   int    retraceBars;
};

FBOSetup g_setup[MAX_LEVELS];
int      g_hATR;
datetime g_lastBar = 0;
datetime g_today = 0;
int      g_tradesToday = 0;
bool     g_inPosition = false;
double   g_entryPrice = 0, g_riskAmount = 0;
int      g_tradeDir = 0;
datetime g_entryTime = 0;
double   g_riskPct  = 1.25;
string   g_riskName = "MEDIUM";
string   g_activeSymbol = "";

bool     g_newsBlackout   = false;
string   g_newsEventName  = "";
datetime g_newsEventTime  = 0;
datetime g_newsLastCheck  = 0;

datetime g_attachTime     = 0;
double   g_dayStartBalance= 0;
double   g_peakEquity     = 0;
int      g_lossesToday    = 0;
bool     g_ddPaused       = false;
bool     g_dayLossPaused  = false;

string   g_dashPrefix     = "DE40X1_";

int      g_hTrailATR = INVALID_HANDLE;
bool     g_partialClosed = false;
bool     g_trailActive = false;
double   g_currentTrailSL = 0;
double   g_mfeR = 0;
datetime g_lastTrailBar = 0;

//=== MODULE G (GOLDILOCKS) STATE ===
int      g_hGlkFast = INVALID_HANDLE;
int      g_hGlkMed  = INVALID_HANDLE;
int      g_hGlkSlow = INVALID_HANDLE;
int      g_hGlkATR  = INVALID_HANDLE;
int      g_glkState = 0;       // 0=scan, 1=pullback armed
int      g_glkDir   = 0;
int      g_glkPullBars = 0;
double   g_glkArmPrice  = 0;
double   g_glkPullExtreme = 0;
bool     g_glkTouch = false;

//=== MODULE H (VWAP/STRUCTURE) STATE ===
int      g_vwState = 0;        // 0=scan, 1=pullback armed
int      g_vwDir   = 0;
int      g_vwPullBars = 0;
double   g_vwArmPrice  = 0;
double   g_vwPullExtreme = 0;
bool     g_vwTouch = false;

long     g_magicGLK  = 0;
long     g_magicVWAP = 0;
int      g_hVwapATR  = INVALID_HANDLE;
int      g_hTrendEMA = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Module enable helper                                              |
//| InpModuleMask==0 -> legacy mode: FBO levels from InpLevelMask,   |
//| GLK/VWAP disabled (v1.00 behaviour, baseline untouched).         |
//+------------------------------------------------------------------+
bool ModOn(int bit)
{
   if(InpModuleMask == 0)
   {
      if(bit <= 5) return ((InpLevelMask & (1 << bit)) != 0);
      return false;
   }
   return ((InpModuleMask & (1 << bit)) != 0);
}

bool OwnMagic(long m)
{
   return (m == (long)InpMagic || m == (long)InpMagic + 1 || m == (long)InpMagic + 2);
}

//+------------------------------------------------------------------+
//| SYMBOL AUTO-DETECTION                                             |
//+------------------------------------------------------------------+
string DetectDE40Symbol()
{
   if(InpSymbolOverride != "")
   {
      if(SymbolSelect(InpSymbolOverride, true))
         return InpSymbolOverride;
      Print("DE40: Override '", InpSymbolOverride, "' not found, auto-detecting");
   }
   string candidates[] = {
      "GER40", "GER40.cash", "GER40+", "DE40", "DE40+",
      "DAX40", "DAX", "Germany40", "DEU40", "DEU40.cash",
      "GER40m", "GER40fs", "DAX.fs", "DE40fs"
   };
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolSelect(candidates[i], true))
      {
         double bid = SymbolInfoDouble(candidates[i], SYMBOL_BID);
         if(bid > 0)
         {
            Print("DE40: Detected symbol: ", candidates[i], " bid=", bid);
            return candidates[i];
         }
      }
   }
   string cur = _Symbol;
   StringToUpper(cur);
   if(StringFind(cur, "GER") >= 0 || StringFind(cur, "DAX") >= 0 ||
      StringFind(cur, "DE40") >= 0 || StringFind(cur, "DEU") >= 0)
      return _Symbol;

   Print("DE40: WARNING - No DE40 symbol found, using chart symbol: ", _Symbol);
   return _Symbol;
}

//+------------------------------------------------------------------+
void LogSymbolSpecs()
{
   Print("=== DE40 Symbol Specifications ===");
   Print("Symbol: ", g_activeSymbol);
   Print("Digits: ", (int)SymbolInfoInteger(g_activeSymbol, SYMBOL_DIGITS));
   Print("Point: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_POINT));
   Print("Tick Size: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_SIZE));
   Print("Tick Value: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_VALUE));
   Print("Contract Size: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_CONTRACT_SIZE));
   Print("Min Lot: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN));
   Print("Max Lot: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MAX));
   Print("Lot Step: ", SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP));
   Print("Stops Level: ", (int)SymbolInfoInteger(g_activeSymbol, SYMBOL_TRADE_STOPS_LEVEL));
   Print("Freeze Level: ", (int)SymbolInfoInteger(g_activeSymbol, SYMBOL_TRADE_FREEZE_LEVEL));
   Print("Spread: ", SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD));
   Print("==================================");
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_activeSymbol = DetectDE40Symbol();
   if(!SymbolSelect(g_activeSymbol, true))
   {
      Print("DE40: FATAL - Cannot select symbol: ", g_activeSymbol);
      return INIT_FAILED;
   }

   g_hATR = iATR(g_activeSymbol, PERIOD_M1, InpATRPeriod);
   if(g_hATR == INVALID_HANDLE) return INIT_FAILED;
   if(InpEnablePartialClose && InpEnableATRTrail)
   {
      g_hTrailATR = iATR(g_activeSymbol, InpTrailTimeframe, InpATRTrailPeriod);
      if(g_hTrailATR == INVALID_HANDLE) return INIT_FAILED;
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   g_magicGLK  = (long)InpMagic + 1;
   g_magicVWAP = (long)InpMagic + 2;

   if(ModOn(6))
   {
      g_hGlkFast = iMA(g_activeSymbol, InpGlkTimeframe, InpGlkFast, 0, MODE_EMA, PRICE_CLOSE);
      g_hGlkMed  = iMA(g_activeSymbol, InpGlkTimeframe, InpGlkMed,  0, MODE_EMA, PRICE_CLOSE);
      g_hGlkSlow = iMA(g_activeSymbol, InpGlkTimeframe, InpGlkSlow, 0, MODE_EMA, PRICE_CLOSE);
      g_hGlkATR  = iATR(g_activeSymbol, InpGlkTimeframe, InpGlkATRPeriod);
      if(g_hGlkFast == INVALID_HANDLE || g_hGlkMed == INVALID_HANDLE ||
         g_hGlkSlow == INVALID_HANDLE || g_hGlkATR == INVALID_HANDLE)
      { Print("DE40: FATAL - GLK indicator handles failed"); return INIT_FAILED; }
   }
   if(ModOn(7))
   {
      g_hVwapATR = iATR(g_activeSymbol, _Period, InpATRPeriod);
      if(g_hVwapATR == INVALID_HANDLE)
      { Print("DE40: FATAL - VWAP chart ATR handle failed"); return INIT_FAILED; }
   }
   if(InpUseNativeConf > 0)
   {
      if(InpNcTrendFilter)
      {
         g_hTrendEMA = iMA(g_activeSymbol, _Period, InpNcTrendPeriod, 0, MODE_EMA, PRICE_CLOSE);
         if(g_hTrendEMA == INVALID_HANDLE)
         { Print("DE40: FATAL - native confluence trend EMA handle failed"); return INIT_FAILED; }
      }
      Print("DE40: Native confluence gate mode=", InpUseNativeConf);
   }

   switch(InpRiskLevel)
   {
      case RISK_OPTIMIZED: g_riskPct = 0.50; g_riskName = "OPTIMIZED"; break;
      case RISK_MEDIUM:    g_riskPct = 1.25; g_riskName = "MEDIUM";    break;
      case RISK_HIGH:      g_riskPct = 2.50; g_riskName = "HIGH";      break;
      case RISK_MAX:       g_riskPct = 5.00; g_riskName = "MAX";       break;
      default:             g_riskPct = 1.25; g_riskName = "MEDIUM";    break;
   }

   g_attachTime      = TimeCurrent();
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_peakEquity      = AccountInfoDouble(ACCOUNT_EQUITY);
   g_lossesToday     = 0;
   g_ddPaused        = false;
   g_dayLossPaused   = false;
   g_newsLastCheck   = 0;

   Print("=== DE40 X1 v2.00 — DAX Eight-Module Research EA ===");
   Print("Symbol: ", g_activeSymbol);
   Print("Risk: ", g_riskName, " ", DoubleToString(g_riskPct, 2), "%");
   Print("ModuleMask: ", InpModuleMask, (InpModuleMask == 0 ? " (legacy LevelMask mode)" : ""));
   Print("LevelMask: ", InpLevelMask);
   Print("SessionMask: ", InpSessionMask);
   Print("OR Anchor: ", InpORAnchorGMT, ":", IntegerToString(InpORAnchorMin, 2, '0'), " GMT");
   Print("Goldilocks: ", ModOn(6) ? "ON" : "off", " | VWAP: ", ModOn(7) ? "ON" : "off");
   Print("Magics: FBO=", InpMagic, " GLK=", g_magicGLK, " VWAP=", g_magicVWAP);
   Print("Confluence: ", InpConfMode > 0 ? "ON" : "OFF");
   Print("FBL Exit: ", InpEnablePartialClose ? "ON" : "OFF");
   LogSymbolSpecs();

   for(int i = 0; i < MAX_LEVELS; i++) ResetSetup(i);
   if(InpConfMode > 0) LoadGCData();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(g_hATR);
   if(g_hTrailATR != INVALID_HANDLE) IndicatorRelease(g_hTrailATR);
   if(g_hGlkFast != INVALID_HANDLE) IndicatorRelease(g_hGlkFast);
   if(g_hGlkMed  != INVALID_HANDLE) IndicatorRelease(g_hGlkMed);
   if(g_hGlkSlow != INVALID_HANDLE) IndicatorRelease(g_hGlkSlow);
   if(g_hGlkATR  != INVALID_HANDLE) IndicatorRelease(g_hGlkATR);
   if(g_hVwapATR != INVALID_HANDLE) IndicatorRelease(g_hVwapATR);
   if(g_hTrendEMA != INVALID_HANDLE) IndicatorRelease(g_hTrendEMA);
   DashCleanup();
}

//+------------------------------------------------------------------+
//| FDAX DATA LOADING                                                 |
//+------------------------------------------------------------------+
void LoadGCData()
{
   int h = FileOpen(InpConfDataFile, FILE_READ|FILE_CSV|FILE_COMMON|FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
   { Print("DE40: ", InpConfDataFile, " not found — confluence bypassed"); return; }
   for(int i = 0; i < 10 && !FileIsEnding(h); i++) FileReadString(h);

   ArrayResize(g_gcTime, GC_MAX_ROWS);
   ArrayResize(g_gcClose, GC_MAX_ROWS);
   ArrayResize(g_gcDelta, GC_MAX_ROWS);
   ArrayResize(g_gcCumDelta, GC_MAX_ROWS);
   ArrayResize(g_gcVwap, GC_MAX_ROWS);
   ArrayResize(g_gcImbalance, GC_MAX_ROWS);
   ArrayResize(g_gcVolume, GC_MAX_ROWS);
   ArrayResize(g_gcVolSpike, GC_MAX_ROWS);
   ArrayResize(g_gcAbsorption, GC_MAX_ROWS);
   ArrayResize(g_gcPdDiv, GC_MAX_ROWS);

   int n = 0;
   while(!FileIsEnding(h) && n < GC_MAX_ROWS)
   {
      string dtStr = FileReadString(h);
      if(dtStr == "" || FileIsEnding(h)) break;
      g_gcTime[n]     = StringToTime(dtStr);
      g_gcClose[n]    = StringToDouble(FileReadString(h));
      g_gcDelta[n]    = StringToDouble(FileReadString(h));
      g_gcCumDelta[n] = StringToDouble(FileReadString(h));
      g_gcVwap[n]     = StringToDouble(FileReadString(h));
      g_gcImbalance[n]= StringToDouble(FileReadString(h));
      g_gcVolume[n]   = StringToDouble(FileReadString(h));
      g_gcVolSpike[n] = StringToDouble(FileReadString(h));
      g_gcAbsorption[n]= StringToDouble(FileReadString(h));
      g_gcPdDiv[n]    = StringToDouble(FileReadString(h));
      if(g_gcTime[n] > 0) n++;
   }
   FileClose(h);
   g_gcRows = n;
   Print("DE40: Loaded ", g_gcRows, " FDAX rows");
}

int GCIndex(datetime gmtTime)
{
   if(g_gcRows < 10) return -1;
   datetime t = gmtTime - (gmtTime % 900);
   int lo = 0, hi = g_gcRows - 1;
   while(lo <= hi)
   {
      int mid = (lo + hi) / 2;
      if(g_gcTime[mid] == t) return mid;
      if(g_gcTime[mid] < t) lo = mid + 1;
      else hi = mid - 1;
   }
   int idx = hi;
   if(idx < 0) idx = 0;
   if(idx >= g_gcRows) idx = g_gcRows - 1;
   if(MathAbs((double)(gmtTime - g_gcTime[idx])) > 3600) return -1;
   return idx;
}

//+------------------------------------------------------------------+
bool ConfluencePass(int dir, int barsToDisp, int retraceBars)
{
   if(InpConfMode == 0) return true;
   if(g_gcRows < 30) return true;

   datetime srvNow = TimeCurrent();
   datetime gmtNow = srvNow - InpServerUTC * 3600;
   int idx = GCIndex(gmtNow);
   if(idx < 20) return true;

   double fdClose = g_gcClose[idx];
   double fdVwap  = g_gcVwap[idx];
   double fdDelta = g_gcDelta[idx];
   double fdVol   = g_gcVolume[idx];

   double vwapDist = 0;
   if(fdVwap > 0) vwapDist = (fdClose - fdVwap) / fdVwap * 10000.0;

   double cumSlope = 0;
   if(idx >= 4) cumSlope = g_gcCumDelta[idx] - g_gcCumDelta[idx - 4];

   double volSma = 0;
   for(int i = idx - 19; i <= idx; i++) volSma += g_gcVolume[i];
   volSma /= 20.0;
   double volRatio = (volSma > 0) ? fdVol / volSma : 1.0;

   double dMean = 0, dStd = 0;
   for(int i = idx - 19; i <= idx; i++) dMean += g_gcDelta[i];
   dMean /= 20.0;
   for(int i = idx - 19; i <= idx; i++) dStd += (g_gcDelta[i] - dMean) * (g_gcDelta[i] - dMean);
   dStd = MathSqrt(dStd / 19.0);
   double deltaZ = (dStd > 0) ? (fdDelta - dMean) / dStd : 0;

   double score = 0;
   bool vwapAligned = false;
   if(dir == 1)
      vwapAligned = (InpVwapSoftThresh > 0) ? (vwapDist > InpVwapSoftThresh) : (vwapDist > 0);
   else
   {
      double shortThresh = (InpVwapGateDir >= 2) ? InpVwapSoftThresh : 0;
      vwapAligned = (shortThresh > 0) ? (vwapDist < -shortThresh) : (vwapDist < 0);
   }
   if(vwapAligned) score += InpW_VwapDist;

   if((dir == 1 && cumSlope > 0) || (dir == -1 && cumSlope < 0)) score += InpW_CumSlope;
   if(volRatio >= InpVolRatioThresh) score += InpW_VolRatio;
   if((dir == 1 && deltaZ > InpDeltaZThresh) || (dir == -1 && deltaZ < -InpDeltaZThresh))
      score += InpW_DeltaZ;
   if(barsToDisp >= InpMinBarsToDisp && retraceBars >= InpMinRetraceBars) score += InpW_Setup;

   if(InpConfMode == 2 && !vwapAligned) return false;
   if(InpVwapGateDir == 1 && dir == 1 && !vwapAligned) return false;
   if(InpVwapGateDir == 2 && dir == -1 && !vwapAligned) return false;
   if(InpVwapGateDir == 3 && !vwapAligned) return false;

   return (score >= InpMinConfScore);
}

//+------------------------------------------------------------------+
void ResetSetup(int idx)
{
   g_setup[idx].state = ST_IDLE;
   g_setup[idx].dir = 0;
   g_setup[idx].level = 0;
   g_setup[idx].rangeHigh = 0;
   g_setup[idx].rangeLow = 0;
   g_setup[idx].boExtreme = 0;
   g_setup[idx].barsOutside = 0;
   g_setup[idx].failBar = 0;
   g_setup[idx].dispSeen = false;
   g_setup[idx].zTop = 0;
   g_setup[idx].zBottom = 0;
   g_setup[idx].armBar = 0;
   g_setup[idx].levelType = idx;
   g_setup[idx].barsToDisp = 0;
   g_setup[idx].retraceBars = 0;
}

//+------------------------------------------------------------------+
//| DE40 SESSION DETECTION                                            |
//+------------------------------------------------------------------+
int DetectSession(int gmtMinOfDay)
{
   // bit0: Frankfurt electronic open
   if((InpSessionMask & 1) != 0 &&
      gmtMinOfDay >= InpFrankStartGMT * 60 && gmtMinOfDay < InpFrankEndGMT * 60)
      return 1;
   // bit1: London open / Xetra cash
   if((InpSessionMask & 2) != 0 &&
      gmtMinOfDay >= InpLdnStartGMT * 60 && gmtMinOfDay < InpLdnEndGMT * 60)
      return 2;
   // bit2: Xetra cash open window
   if((InpSessionMask & 4) != 0 &&
      gmtMinOfDay >= InpXetraStartGMT * 60 && gmtMinOfDay < InpXetraEndGMT * 60)
      return 3;
   // bit3: US/London overlap
   if((InpSessionMask & 8) != 0 &&
      gmtMinOfDay >= InpUSOvlpStartGMT * 60 + InpUSOvlpStartMin &&
      gmtMinOfDay <  InpUSOvlpEndGMT * 60 + InpUSOvlpEndMin)
      return 4;
   return 0;
}

double GetATR()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hATR, 0, 0, 3, buf) < 3) return 0;
   return buf[1];
}

//+------------------------------------------------------------------+
bool RangeGmt(int startGmtHour, int startMin, int endGmtHour, int endMin,
              double &hi, double &lo)
{
   if(g_today == 0) return false;
   int sSrv = ((startGmtHour + InpServerUTC) % 24) * 60 + startMin;
   int eSrv = ((endGmtHour + InpServerUTC) % 24) * 60 + endMin;
   if(eSrv <= sSrv) return false;
   datetime tStart = g_today + (datetime)(sSrv * 60);
   datetime tEnd   = g_today + (datetime)(eSrv * 60);
   if(TimeCurrent() < tEnd) return false;
   int startShift = iBarShift(g_activeSymbol, PERIOD_M1, tStart, false);
   int lastShift  = iBarShift(g_activeSymbol, PERIOD_M1, tEnd - 60, false);
   if(startShift < 0 || lastShift < 1 || startShift < lastShift) return false;
   int cnt = startShift - lastShift + 1;
   int hIdx = iHighest(g_activeSymbol, PERIOD_M1, MODE_HIGH, cnt, lastShift);
   int lIdx = iLowest(g_activeSymbol, PERIOD_M1, MODE_LOW, cnt, lastShift);
   if(hIdx < 0 || lIdx < 0) return false;
   hi = iHigh(g_activeSymbol, PERIOD_M1, hIdx);
   lo = iLow(g_activeSymbol, PERIOD_M1, lIdx);
   return (hi > lo);
}

//+------------------------------------------------------------------+
double FindEqualLevel(int dir, double atr)
{
   int lb = InpEqSwingLb;
   int need = InpEqScanBars + 2 * lb + 2;
   double hi[], lo[];
   if(CopyHigh(g_activeSymbol, PERIOD_M1, 1, need, hi) < need) return 0;
   if(CopyLow(g_activeSymbol, PERIOD_M1, 1, need, lo) < need) return 0;
   ArraySetAsSeries(hi, true);
   ArraySetAsSeries(lo, true);
   double p1 = 0, p2 = 0;
   for(int i = lb; i < InpEqScanBars + lb; i++)
   {
      bool piv = true;
      for(int k = 1; k <= lb; k++)
      {
         if(dir == 1)
         { if(hi[i] <= hi[i-k] || hi[i] < hi[i+k]) { piv = false; break; } }
         else
         { if(lo[i] >= lo[i-k] || lo[i] > lo[i+k]) { piv = false; break; } }
      }
      if(!piv) continue;
      double v = (dir == 1) ? hi[i] : lo[i];
      if(p1 == 0) { p1 = v; continue; }
      p2 = v; break;
   }
   if(p1 == 0 || p2 == 0) return 0;
   if(MathAbs(p1 - p2) > InpEqTolATR * atr) return 0;
   return (dir == 1) ? MathMax(p1, p2) : MathMin(p1, p2);
}

//+------------------------------------------------------------------+
bool GetLevelsForType(int lvType, double atr, double &lh, double &ll)
{
   lh = 0; ll = 0;
   if(lvType >= 0 && lvType <= 2)
   {
      int mins = (lvType == 0) ? 5 : (lvType == 1) ? 10 : 15;
      int endMin = InpORAnchorMin + mins;
      int endHour = InpORAnchorGMT + endMin / 60;
      endMin %= 60;
      return RangeGmt(InpORAnchorGMT, InpORAnchorMin, endHour, endMin, lh, ll);
   }
   if(lvType == 3)
      return RangeGmt(InpAsiaStartGMT, 0, InpAsiaEndGMT, 0, lh, ll);
   if(lvType == 4)
      return RangeGmt(InpPreLdnStartGMT, 0, InpPreLdnEndGMT, 0, lh, ll);
   if(lvType == 5)
   {
      lh = iHigh(g_activeSymbol, PERIOD_D1, 1);
      ll = iLow(g_activeSymbol, PERIOD_D1, 1);
      return (lh > ll && lh > 0);
   }
   if(lvType == 6)
   {
      lh = FindEqualLevel(1, atr);
      ll = FindEqualLevel(-1, atr);
      return (lh > 0 && ll > 0 && lh > ll);
   }
   return false;
}

//+------------------------------------------------------------------+
//| FBO STATE MACHINE                                                 |
//+------------------------------------------------------------------+
void StageIdle(int idx, double atr)
{
   double lh, ll;
   if(!GetLevelsForType(idx, atr, lh, ll)) return;

   double c1 = iClose(g_activeSymbol, PERIOD_M1, 1);
   double h1 = iHigh(g_activeSymbol, PERIOD_M1, 1);
   double l1 = iLow(g_activeSymbol, PERIOD_M1, 1);

   if(c1 > lh + InpMinBreakATR * atr)
   {
      if(h1 > lh + InpMaxBreakATR * atr) return;
      g_setup[idx].state = ST_BREAKOUT;
      g_setup[idx].dir = -1;
      g_setup[idx].level = lh;
      g_setup[idx].rangeHigh = lh;
      g_setup[idx].rangeLow = ll;
      g_setup[idx].boExtreme = h1;
      g_setup[idx].barsOutside = 1;
      return;
   }
   if(c1 < ll - InpMinBreakATR * atr)
   {
      if(l1 < ll - InpMaxBreakATR * atr) return;
      g_setup[idx].state = ST_BREAKOUT;
      g_setup[idx].dir = 1;
      g_setup[idx].level = ll;
      g_setup[idx].rangeHigh = lh;
      g_setup[idx].rangeLow = ll;
      g_setup[idx].boExtreme = l1;
      g_setup[idx].barsOutside = 1;
   }
}

void StageBreakout(int idx, double atr)
{
   double c1 = iClose(g_activeSymbol, PERIOD_M1, 1);
   double h1 = iHigh(g_activeSymbol, PERIOD_M1, 1);
   double l1 = iLow(g_activeSymbol, PERIOD_M1, 1);

   if(g_setup[idx].dir == -1)
   {
      if(h1 > g_setup[idx].level + InpMaxBreakATR * atr) { ResetSetup(idx); return; }
      g_setup[idx].boExtreme = MathMax(g_setup[idx].boExtreme, h1);
      if(c1 > g_setup[idx].level)
      {
         g_setup[idx].barsOutside++;
         if(g_setup[idx].barsOutside > InpMaxBarsOutside) ResetSetup(idx);
         return;
      }
      g_setup[idx].state = ST_FAILED;
      g_setup[idx].failBar = Bars(g_activeSymbol, PERIOD_M1);
      g_setup[idx].dispSeen = false;
   }
   else
   {
      if(l1 < g_setup[idx].level - InpMaxBreakATR * atr) { ResetSetup(idx); return; }
      g_setup[idx].boExtreme = MathMin(g_setup[idx].boExtreme, l1);
      if(c1 < g_setup[idx].level)
      {
         g_setup[idx].barsOutside++;
         if(g_setup[idx].barsOutside > InpMaxBarsOutside) ResetSetup(idx);
         return;
      }
      g_setup[idx].state = ST_FAILED;
      g_setup[idx].failBar = Bars(g_activeSymbol, PERIOD_M1);
      g_setup[idx].dispSeen = false;
   }
}

void StageFailed(int idx, double atr)
{
   int barsSinceFail = Bars(g_activeSymbol, PERIOD_M1) - g_setup[idx].failBar;
   if(barsSinceFail > InpMaxBarsToIfvg) { ResetSetup(idx); return; }
   if(!g_setup[idx].dispSeen && barsSinceFail > InpMaxBarsToDisp) { ResetSetup(idx); return; }

   double o1 = iOpen(g_activeSymbol, PERIOD_M1, 1);
   double c1 = iClose(g_activeSymbol, PERIOD_M1, 1);
   double body = MathAbs(c1 - o1);

   if(!g_setup[idx].dispSeen)
   {
      if(g_setup[idx].dir == -1 && c1 < o1 && c1 < g_setup[idx].level && body >= InpDispBodyATR * atr)
      { g_setup[idx].dispSeen = true; g_setup[idx].barsToDisp = barsSinceFail; }
      else if(g_setup[idx].dir == 1 && c1 > o1 && c1 > g_setup[idx].level && body >= InpDispBodyATR * atr)
      { g_setup[idx].dispSeen = true; g_setup[idx].barsToDisp = barsSinceFail; }
   }
   if(!g_setup[idx].dispSeen) return;

   double zTop, zBottom;
   if(InpUseIFVG)
   {
      if(!FindIFVG(g_setup[idx].dir, atr, c1, zTop, zBottom)) return;
      double zoneMid = (zTop + zBottom) / 2.0;
      if(MathAbs(zoneMid - g_setup[idx].level) > InpMaxIfvgDistATR * atr) return;
   }
   else
   {
      if(g_setup[idx].dir == -1) { zTop = o1; zBottom = c1; }
      else                       { zTop = c1; zBottom = o1; }
      if(zTop - zBottom < 0.1 * atr)
      {
         double mid = (zTop + zBottom) / 2.0;
         zTop = mid + 0.05 * atr;
         zBottom = mid - 0.05 * atr;
      }
   }

   g_setup[idx].zTop = zTop;
   g_setup[idx].zBottom = zBottom;
   g_setup[idx].state = ST_ARMED;
   g_setup[idx].armBar = Bars(g_activeSymbol, PERIOD_M1);
}

bool FindIFVG(int dir, double atr, double dispClose, double &zTop, double &zBottom)
{
   int need = InpIfvgScanBars + 3;
   double hi[], lo[], op[], cl[];
   if(CopyHigh(g_activeSymbol, PERIOD_M1, 1, need, hi) < need) return false;
   if(CopyLow(g_activeSymbol, PERIOD_M1, 1, need, lo) < need) return false;
   if(CopyOpen(g_activeSymbol, PERIOD_M1, 1, need, op) < need) return false;
   if(CopyClose(g_activeSymbol, PERIOD_M1, 1, need, cl) < need) return false;
   ArraySetAsSeries(hi, true); ArraySetAsSeries(lo, true);
   ArraySetAsSeries(op, true); ArraySetAsSeries(cl, true);
   double minGap = InpMinGapATR * atr;

   if(dir == -1)
   {
      if(lo[2] - hi[0] >= minGap && cl[1] < op[1])
      { zTop = lo[2]; zBottom = hi[0]; NormZ(zTop, zBottom); return true; }
      for(int i = 1; i < InpIfvgScanBars; i++)
      {
         if(lo[i] - hi[i+2] >= minGap && cl[i+1] > op[i+1] && dispClose < hi[i+2])
         { zTop = lo[i]; zBottom = hi[i+2]; NormZ(zTop, zBottom); return true; }
      }
   }
   else
   {
      if(lo[0] - hi[2] >= minGap && cl[1] > op[1])
      { zTop = lo[0]; zBottom = hi[2]; NormZ(zTop, zBottom); return true; }
      for(int i = 1; i < InpIfvgScanBars; i++)
      {
         if(lo[i+2] - hi[i] >= minGap && cl[i+1] < op[i+1] && dispClose > lo[i+2])
         { zTop = lo[i+2]; zBottom = hi[i]; NormZ(zTop, zBottom); return true; }
      }
   }
   return false;
}

void NormZ(double &zTop, double &zBottom)
{ if(zTop < zBottom) { double t = zTop; zTop = zBottom; zBottom = t; } }

void StageArmed(int idx, double atr)
{
   int barsSinceArm = Bars(g_activeSymbol, PERIOD_M1) - g_setup[idx].armBar;
   if(barsSinceArm > InpMaxRetraceBars) { ResetSetup(idx); return; }

   double o1 = iOpen(g_activeSymbol, PERIOD_M1, 1);
   double c1 = iClose(g_activeSymbol, PERIOD_M1, 1);
   double h1 = iHigh(g_activeSymbol, PERIOD_M1, 1);
   double l1 = iLow(g_activeSymbol, PERIOD_M1, 1);
   bool triggered = false;

   if(g_setup[idx].dir == -1)
   {
      if(c1 > g_setup[idx].zTop) { ResetSetup(idx); return; }
      double mid = (g_setup[idx].zTop + g_setup[idx].zBottom) / 2.0;
      double fill = g_setup[idx].zBottom + InpFillFraction * (g_setup[idx].zTop - g_setup[idx].zBottom);
      switch(InpEntryMode)
      {
         case 0: triggered = (h1 >= g_setup[idx].zBottom); break;
         case 1: triggered = (h1 >= mid); break;
         case 2: triggered = (h1 >= fill); break;
         case 3: triggered = (h1 >= g_setup[idx].zBottom && c1 < g_setup[idx].zBottom && c1 < o1); break;
         case 4:
            if(h1 >= g_setup[idx].zBottom && c1 < g_setup[idx].zBottom && c1 < o1)
            { int li = iLowest(g_activeSymbol, PERIOD_M1, MODE_LOW, InpStructShiftBars, 2);
              if(li >= 0 && c1 < iLow(g_activeSymbol, PERIOD_M1, li)) triggered = true; }
            break;
      }
   }
   else
   {
      if(c1 < g_setup[idx].zBottom) { ResetSetup(idx); return; }
      double mid = (g_setup[idx].zTop + g_setup[idx].zBottom) / 2.0;
      double fill = g_setup[idx].zTop - InpFillFraction * (g_setup[idx].zTop - g_setup[idx].zBottom);
      switch(InpEntryMode)
      {
         case 0: triggered = (l1 <= g_setup[idx].zTop); break;
         case 1: triggered = (l1 <= mid); break;
         case 2: triggered = (l1 <= fill); break;
         case 3: triggered = (l1 <= g_setup[idx].zTop && c1 > g_setup[idx].zTop && c1 > o1); break;
         case 4:
            if(l1 <= g_setup[idx].zTop && c1 > g_setup[idx].zTop && c1 > o1)
            { int hi2 = iHighest(g_activeSymbol, PERIOD_M1, MODE_HIGH, InpStructShiftBars, 2);
              if(hi2 >= 0 && c1 > iHigh(g_activeSymbol, PERIOD_M1, hi2)) triggered = true; }
            break;
      }
   }

   if(triggered)
   {
      int retraceBars = barsSinceArm;
      if(!ConfluencePass(g_setup[idx].dir, g_setup[idx].barsToDisp, retraceBars))
      { ResetSetup(idx); return; }
      if(!NativeConfluencePass(g_setup[idx].dir))
      { ResetSetup(idx); return; }
      ExecuteEntry(idx, atr);
      ResetSetup(idx);
   }
}

//+------------------------------------------------------------------+
void ExecuteEntry(int idx, double atr)
{
   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return;

   int dir = g_setup[idx].dir;
   double entry, sl;
   if(dir == 1)
   {
      entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
      sl = (InpSLMode == 0) ? g_setup[idx].boExtreme - InpSL_BufferATR * atr
         : (InpSLMode == 1) ? entry - InpSL_ATR * atr
                            : g_setup[idx].zBottom - InpSL_BufferATR * atr;
   }
   else
   {
      entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
      sl = (InpSLMode == 0) ? g_setup[idx].boExtreme + InpSL_BufferATR * atr
         : (InpSLMode == 1) ? entry + InpSL_ATR * atr
                            : g_setup[idx].zTop + InpSL_BufferATR * atr;
   }

   double risk = MathAbs(entry - sl);
   if(risk <= 0 || risk > 5.0 * atr) return;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return;

   double tp = 0;
   if(InpTPMode == 0 && g_setup[idx].rangeHigh > g_setup[idx].rangeLow)
      tp = (g_setup[idx].rangeHigh + g_setup[idx].rangeLow) / 2.0;
   else if(InpTPMode == 1 && g_setup[idx].rangeHigh > g_setup[idx].rangeLow)
      tp = (dir == 1) ? g_setup[idx].rangeHigh : g_setup[idx].rangeLow;
   else if(InpTPMode == 2)
      tp = NearestLiquidity(idx, dir, entry);

   bool tpValid = (tp > 0) &&
                  ((dir == 1 && tp > entry) || (dir == -1 && tp < entry)) &&
                  (MathAbs(tp - entry) >= 0.5 * risk);
   if(!tpValid)
      tp = (dir == 1) ? entry + risk * InpTP_RR : entry - risk * InpTP_RR;

   if(InpEnablePartialClose) tp = 0;

   double lots = CalcLots(risk);
   if(lots <= 0) return;

   string comment = StringFormat("DX1_%d_%s", idx, (dir == 1) ? "L" : "S");
   if(dir == -1 && !InpFboAllowShort) return;
   bool ok = (dir == 1) ? trade.Buy(lots, g_activeSymbol, entry, sl, tp, comment)
                         : trade.Sell(lots, g_activeSymbol, entry, sl, tp, comment);
   if(ok)
   {
      g_inPosition = true;
      g_tradesToday++;
      double fill = trade.ResultPrice();
      g_entryPrice = (fill > 0) ? fill : entry;
      g_riskAmount = risk;
      g_tradeDir = dir;
      g_entryTime = TimeCurrent();
      g_partialClosed = false;
      g_trailActive = false;
      g_currentTrailSL = 0;
      g_mfeR = 0;
      g_lastTrailBar = 0;

      MqlDateTime dtLog; TimeToStruct(TimeCurrent(), dtLog);
      int logGmtH = dtLog.hour - InpServerUTC;
      if(logGmtH < 0) logGmtH += 24;
      Print("TRADE_APPROVED | ", g_activeSymbol, " | ", (dir==1)?"BUY":"SELL",
            " | lots=", DoubleToString(lots, 2),
            " | entry=", DoubleToString(g_entryPrice, _Digits),
            " | sl=", DoubleToString(sl, _Digits),
            " | risk=", DoubleToString(risk, _Digits),
            " | R=", DoubleToString(risk / atr, 2), "ATR",
            " | gmt=", IntegerToString(logGmtH), ":", IntegerToString(dtLog.min));
   }
}

double NearestLiquidity(int idx, int dir, double entry)
{
   double cand[8]; int n = 0;
   double pdh = iHigh(g_activeSymbol, PERIOD_D1, 1);
   double pdl = iLow(g_activeSymbol, PERIOD_D1, 1);
   if(pdh > 0) cand[n++] = pdh;
   if(pdl > 0) cand[n++] = pdl;
   double ah, al;
   if(RangeGmt(InpAsiaStartGMT, 0, InpAsiaEndGMT, 0, ah, al))
   { cand[n++] = ah; cand[n++] = al; }
   if(g_setup[idx].rangeHigh > 0) cand[n++] = g_setup[idx].rangeHigh;
   if(g_setup[idx].rangeLow > 0)  cand[n++] = g_setup[idx].rangeLow;
   double best = 0;
   for(int i = 0; i < n; i++)
   {
      if(dir == -1 && cand[i] < entry)
      { if(best == 0 || cand[i] > best) best = cand[i]; }
      else if(dir == 1 && cand[i] > entry)
      { if(best == 0 || cand[i] < best) best = cand[i]; }
   }
   return best;
}

//+------------------------------------------------------------------+
//| RISK CALCULATION (DE40-aware)                                     |
//+------------------------------------------------------------------+
double CalcLots(double risk)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * g_riskPct / 100.0;
   double tickVal = SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(g_activeSymbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || risk <= 0) return 0;
   double lots = riskMoney / (risk / tickSize * tickVal);
   double minLot = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);
   return lots;
}

//+------------------------------------------------------------------+
void ResetExitState()
{
   g_inPosition = false;
   g_partialClosed = false;
   g_trailActive = false;
   g_currentTrailSL = 0;
   g_mfeR = 0;
   g_lastTrailBar = 0;
   g_tradeDir = 0;
   g_riskAmount = 0;
   g_entryPrice = 0;
}

double GetTrailATR()
{
   if(g_hTrailATR == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hTrailATR, 0, 0, 3, buf) < 3) return 0;
   return buf[1];
}

//+------------------------------------------------------------------+
//| POSITION MANAGEMENT (FBL exit)                                    |
//+------------------------------------------------------------------+
void ManagePosition()
{
   if(!g_inPosition) return;
   bool found = false;
   ulong myTicket = 0;
   double posVolume = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_activeSymbol) continue;
      if(OwnMagic(PositionGetInteger(POSITION_MAGIC)))
      { found = true; myTicket = tk; posVolume = PositionGetDouble(POSITION_VOLUME); break; }
   }
   if(!found) { TrackClose(); ResetExitState(); return; }

   if(InpTimeStopMin > 0)
   {
      int elapsed = (int)((TimeCurrent() - g_entryTime) / 60);
      if(elapsed >= InpTimeStopMin)
      { trade.PositionClose(myTicket); ResetExitState(); return; }
   }

   if(!InpEnablePartialClose) return;
   if(g_riskAmount <= 0 || g_tradeDir == 0) return;

   double cur = (g_tradeDir == 1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_BID)
                                   : SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
   double profitR = (g_tradeDir == 1) ? (cur - g_entryPrice) / g_riskAmount
                                       : (g_entryPrice - cur) / g_riskAmount;
   if(profitR > g_mfeR) g_mfeR = profitR;

   // TP1: partial close + BE move
   if(!g_partialClosed)
   {
      if(profitR < InpPartialTargetR) return;
      double step = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_STEP);
      double minL = SymbolInfoDouble(g_activeSymbol, SYMBOL_VOLUME_MIN);
      double closeLots = MathFloor(posVolume * InpPartialPercent / 100.0 / step) * step;
      if(closeLots < minL || posVolume - closeLots < minL - 1e-8)
      {
         trade.PositionClose(myTicket);
         ResetExitState();
         return;
      }
      if(!trade.PositionClosePartial(myTicket, closeLots)) return;
      g_partialClosed = true;
      if(InpMoveRunnerToBE && PositionSelectByTicket(myTicket))
      {
         double beSL = (g_tradeDir == 1)
                       ? g_entryPrice + InpBECostBuffer * g_riskAmount
                       : g_entryPrice - InpBECostBuffer * g_riskAmount;
         beSL = NormalizeDouble(beSL, _Digits);
         double curSL = PositionGetDouble(POSITION_SL);
         bool better = (g_tradeDir == 1) ? (beSL > curSL)
                                         : (beSL < curSL || curSL == 0);
         if(better && trade.PositionModify(myTicket, beSL, PositionGetDouble(POSITION_TP)))
            g_currentTrailSL = beSL;
      }
      return;
   }

   // Runner hard-cap
   if(InpRunnerMaxR > 0 && profitR >= InpRunnerMaxR)
   {
      trade.PositionClose(myTicket);
      ResetExitState();
      return;
   }

   // ATR trail
   if(!InpEnableATRTrail) return;
   if(!g_trailActive && g_mfeR >= InpTrailActivationR) g_trailActive = true;
   if(!g_trailActive) return;
   datetime tb = iTime(g_activeSymbol, InpTrailTimeframe, 0);
   if(tb <= 0 || tb == g_lastTrailBar) return;
   g_lastTrailBar = tb;
   double atrTrail = GetTrailATR();
   if(atrTrail <= 0) return;
   double c1 = iClose(g_activeSymbol, InpTrailTimeframe, 1);
   double newSL = (g_tradeDir == 1) ? c1 - InpATRTrailMultiplier * atrTrail
                                     : c1 + InpATRTrailMultiplier * atrTrail;
   newSL = NormalizeDouble(newSL, _Digits);
   if(!PositionSelectByTicket(myTicket)) return;
   double curSL = PositionGetDouble(POSITION_SL);
   bool improve = (g_tradeDir == 1) ? (newSL > curSL)
                                     : (newSL < curSL || curSL == 0);
   if(improve && trade.PositionModify(myTicket, newSL, PositionGetDouble(POSITION_TP)))
      g_currentTrailSL = newSL;
}

//+------------------------------------------------------------------+
//| NEWS AVOIDANCE                                                    |
//+------------------------------------------------------------------+
void CheckNews()
{
   g_newsBlackout = false;
   g_newsEventName = "";
   g_newsEventTime = 0;
   if(!InpNewsAvoid) return;

   string countries[];
   int nc = StringSplit(InpNewsCurrencies, ',', countries);
   datetime from = TimeCurrent() - (datetime)(InpNewsWindow * 60);
   datetime to   = TimeCurrent() + (datetime)(InpNewsWindow * 60);

   for(int c = 0; c < nc; c++)
   {
      string country = "";
      string cur = countries[c];
      StringTrimLeft(cur); StringTrimRight(cur);
      if(cur == "USD") country = "United States";
      else if(cur == "EUR") country = "Germany";
      else if(cur == "GBP") country = "United Kingdom";
      else if(cur == "JPY") country = "Japan";
      else if(cur == "CHF") country = "Switzerland";
      else if(cur == "AUD") country = "Australia";
      else if(cur == "CAD") country = "Canada";
      else if(cur == "NZD") country = "New Zealand";
      else continue;

      MqlCalendarEvent events[];
      int evtCount = CalendarEventByCountry(country, events);
      if(evtCount <= 0) continue;

      for(int e = 0; e < evtCount; e++)
      {
         if((int)events[e].importance < InpNewsImpact) continue;
         MqlCalendarValue vals[];
         int vCount = CalendarValueHistory(vals, from, to, events[e].event_code, NULL);
         if(vCount > 0)
         {
            g_newsBlackout = true;
            g_newsEventName = events[e].name;
            g_newsEventTime = vals[0].time;
            return;
         }
      }
   }
}

//+------------------------------------------------------------------+
void TrackClose()
{
   if(g_tradeDir == 0 || g_entryPrice == 0) return;
   double exitPrice = 0;
   HistorySelect(g_today, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   for(int i = totalDeals - 1; i >= 0; i--)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(dt == 0) continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != g_activeSymbol) continue;
      if(!OwnMagic(HistoryDealGetInteger(dt, DEAL_MAGIC))) continue;
      if(HistoryDealGetInteger(dt, DEAL_ENTRY) == DEAL_ENTRY_OUT ||
         HistoryDealGetInteger(dt, DEAL_ENTRY) == DEAL_ENTRY_INOUT)
      {
         exitPrice = HistoryDealGetDouble(dt, DEAL_PRICE);
         break;
      }
   }
   if(exitPrice <= 0) return;

   double pnl = (g_tradeDir == 1) ? (exitPrice - g_entryPrice) : (g_entryPrice - exitPrice);
   if(pnl < 0)
   {
      g_lossesToday++;
      Print("LOSS_TRACKED | count=", g_lossesToday, "/", InpStopLossDay);
      if(InpStopLossDay > 0 && g_lossesToday >= InpStopLossDay)
      {
         g_dayLossPaused = true;
         Print("DAILY LOSS LIMIT REACHED");
      }
   }
}

//+------------------------------------------------------------------+
//| ON TICK                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime curBar = iTime(g_activeSymbol, PERIOD_M1, 0);
   if(curBar == g_lastBar) return;
   g_lastBar = curBar;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6) return;

   int gmtHour = dt.hour - InpServerUTC;
   if(gmtHour < 0) gmtHour += 24;
   if(gmtHour >= 24) gmtHour -= 24;
   int gmtMinOfDay = gmtHour * 60 + dt.min;

   datetime newToday = StringToTime(IntegerToString(dt.year) + "." +
                        IntegerToString(dt.mon) + "." + IntegerToString(dt.day));
   if(newToday != g_today)
   {
      g_today = newToday;
      g_tradesToday = 0;
      g_lossesToday = 0;
      g_dayLossPaused = false;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      for(int i = 0; i < MAX_LEVELS; i++) ResetSetup(i);
      g_glkState = 0; g_glkDir = 0; g_glkPullBars = 0; g_glkTouch = false;
      g_vwState  = 0; g_vwDir  = 0; g_vwPullBars  = 0; g_vwTouch  = false;
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_peakEquity) g_peakEquity = equity;
   if(InpDDCutPct > 0 && g_peakEquity > 0)
   {
      double ddPct = (g_peakEquity - equity) / g_peakEquity * 100.0;
      g_ddPaused = (ddPct >= InpDDCutPct);
   }

   if(InpNewsAvoid && TimeCurrent() > g_newsLastCheck + 300)
   {
      g_newsLastCheck = TimeCurrent();
      CheckNews();
   }

   ManagePosition();
   if(g_inPosition) { DashUpdate(); return; }

   DashUpdate();

   if(TimeCurrent() - g_attachTime < InpColdStartSec) return;
   if(g_newsBlackout) return;
   if(g_dayLossPaused) return;
   if(g_ddPaused) return;

   int session = DetectSession(gmtMinOfDay);
   if(session == 0) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   double atr = GetATR();
   if(atr <= 0 || atr < InpMinATR || atr > InpMaxATR) return;

   for(int lv = 0; lv < MAX_LEVELS; lv++)
   {
      // Legacy mode (ModuleMask==0): levels gated by InpLevelMask incl. EqHL(6).
      // Module mode: bits 0..5 select FBO modules A-F; bit 6 is GLK (not a level).
      bool lvOn = (InpModuleMask == 0) ? ((InpLevelMask & (1 << lv)) != 0)
                                       : ((lv <= 5) && ((InpModuleMask & (1 << lv)) != 0));
      if(!lvOn) continue;
      switch(g_setup[lv].state)
      {
         case ST_IDLE:     StageIdle(lv, atr);     break;
         case ST_BREAKOUT: StageBreakout(lv, atr); break;
         case ST_FAILED:   StageFailed(lv, atr);   break;
         case ST_ARMED:    StageArmed(lv, atr);    break;
      }
      if(g_inPosition) return;
      if(g_tradesToday >= InpMaxTradesDay) return;
   }

   // Continuation modules G (Goldilocks) and H (VWAP/structure)
   if(!g_inPosition && g_tradesToday < InpMaxTradesDay && ModOn(6))
      GlkEngine(atr);
   if(!g_inPosition && g_tradesToday < InpMaxTradesDay && ModOn(7))
      VwapEngine(atr);
}

//+------------------------------------------------------------------+
//| NATIVE ENTRY-QUALITY GATE (no external feed)                     |
//| Mode 0 = off; 1 = score >= InpNcMinScore; 2 = hard gate (all).   |
//+------------------------------------------------------------------+
bool NativeConfluencePass(int dir)
{
   if(InpUseNativeConf == 0) return true;
   double score = 0;
   int checks = 0;
   double c1 = iClose(g_activeSymbol, _Period, 1);

   if(InpNcTrendFilter && g_hTrendEMA != INVALID_HANDLE)
   {
      double ema[];
      ArraySetAsSeries(ema, true);
      if(CopyBuffer(g_hTrendEMA, 0, 1, 1, ema) == 1)
      {
         checks++;
         if((dir == 1 && c1 > ema[0]) || (dir == -1 && c1 < ema[0])) score += 1.0;
         else if(InpUseNativeConf == 2) return false;
      }
   }
   if(InpNcVwapSide)
   {
      double vwap = 0;
      if(VwapCalc(0, vwap))
      {
         checks++;
         if((dir == 1 && c1 > vwap) || (dir == -1 && c1 < vwap)) score += 1.0;
         else if(InpUseNativeConf == 2) return false;
      }
   }
   if(InpNcVolSpike)
   {
      double vol1 = (double)iVolume(g_activeSymbol, PERIOD_M1, 1);
      double avg = 0;
      for(int i = 2; i <= 21; i++) avg += (double)iVolume(g_activeSymbol, PERIOD_M1, i);
      avg /= 20.0;
      if(avg > 0)
      {
         checks++;
         if(vol1 >= InpNcVolMult * avg) score += 1.0;
         else if(InpUseNativeConf == 2) return false;
      }
   }
   if(checks == 0) return true;
   if(InpUseNativeConf == 2) return true;
   return (score >= InpNcMinScore);
}

//+------------------------------------------------------------------+
//| SHARED MODULE ENTRY PLACEMENT (G/H)                               |
//+------------------------------------------------------------------+
bool PlaceModuleEntry(int dir, double sl, double rr, string comment, long magic)
{
   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return false;

   double entry = (dir == 1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK)
                             : SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
   double risk = MathAbs(entry - sl);
   if(risk <= 0) return false;
   if((dir == 1 && sl >= entry) || (dir == -1 && sl <= entry)) return false;

   double tp = (dir == 1) ? entry + risk * rr : entry - risk * rr;
   if(InpEnablePartialClose) tp = 0;   // FBL runner management takes over

   double lots = CalcLots(risk);
   if(lots <= 0) return false;

   trade.SetExpertMagicNumber(magic);
   bool ok = (dir == 1) ? trade.Buy(lots, g_activeSymbol, entry, sl, tp, comment)
                        : trade.Sell(lots, g_activeSymbol, entry, sl, tp, comment);
   trade.SetExpertMagicNumber(InpMagic);
   if(!ok) { Print("MODULE_ENTRY_REJECTED | ", comment); return false; }

   g_inPosition = true;
   g_tradesToday++;
   double fill = trade.ResultPrice();
   g_entryPrice = (fill > 0) ? fill : entry;
   g_riskAmount = risk;
   g_tradeDir = dir;
   g_entryTime = TimeCurrent();
   g_partialClosed = false;
   g_trailActive = false;
   g_currentTrailSL = 0;
   g_mfeR = 0;
   g_lastTrailBar = 0;
   Print("TRADE_APPROVED | ", g_activeSymbol, " | ", comment,
         " | ", (dir == 1) ? "BUY" : "SELL",
         " | lots=", DoubleToString(lots, 2),
         " | entry=", DoubleToString(g_entryPrice, _Digits),
         " | sl=", DoubleToString(sl, _Digits),
         " | magic=", IntegerToString(magic));
   return true;
}

int ContGmtMinOfDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour - InpServerUTC;
   if(h < 0) h += 24;
   if(h >= 24) h -= 24;
   return h * 60 + dt.min;
}

//+------------------------------------------------------------------+
//| MODULE G: GOLDILOCKS EMA PULLBACK CONTINUATION                    |
//| Method (transferred from USDCHF GLK research, NOT parameters):    |
//| stacked EMA alignment persisted N bars, fast-med and med-slow     |
//| separation inside an ATR-banded "just right" zone, separation     |
//| slope persistence, then pullback into the MA zone + rejection.    |
//+------------------------------------------------------------------+
void GlkReset()
{
   g_glkState = 0;
   g_glkDir = 0;
   g_glkPullBars = 0;
   g_glkArmPrice = 0;
   g_glkPullExtreme = 0;
   g_glkTouch = false;
}

void GlkEngine(double atrM1)
{
   static datetime glkLastBar = 0;
   datetime glkBar = iTime(g_activeSymbol, InpGlkTimeframe, 0);
   if(glkBar <= 0 || glkBar == glkLastBar) return;
   glkLastBar = glkBar;

   int gmtMin = ContGmtMinOfDay();
   if(gmtMin < InpGlkStartGMT * 60 || gmtMin >= InpGlkEndGMT * 60)
   { if(g_glkState != 0) GlkReset(); return; }

   int need = MathMax(InpGlkPersist, InpGlkSlopeLb + 1) + 1;
   double f[], m[], s[], av[];
   ArraySetAsSeries(f, true); ArraySetAsSeries(m, true);
   ArraySetAsSeries(s, true); ArraySetAsSeries(av, true);
   if(CopyBuffer(g_hGlkFast, 0, 1, need, f) < need) return;
   if(CopyBuffer(g_hGlkMed,  0, 1, need, m) < need) return;
   if(CopyBuffer(g_hGlkSlow, 0, 1, need, s) < need) return;
   if(CopyBuffer(g_hGlkATR,  0, 1, need, av) < need) return;
   double glkATR = av[0];
   if(glkATR <= 0 || glkATR < InpMinATR || glkATR > InpMaxATR) return;

   double c1 = iClose(g_activeSymbol, InpGlkTimeframe, 1);
   double o1 = iOpen(g_activeSymbol, InpGlkTimeframe, 1);
   double h1 = iHigh(g_activeSymbol, InpGlkTimeframe, 1);
   double l1 = iLow(g_activeSymbol, InpGlkTimeframe, 1);

   if(g_glkState == 0)
   {
      bool stackedUp = true, stackedDn = true;
      for(int i = 0; i < InpGlkPersist; i++)
      {
         if(!(f[i] > m[i] && m[i] > s[i])) stackedUp = false;
         if(!(f[i] < m[i] && m[i] < s[i])) stackedDn = false;
      }
      int dir = 0;
      if(stackedUp && c1 > f[0]) dir = 1;
      else if(stackedDn && c1 < f[0] && InpGlkAllowShort) dir = -1;
      if(dir == 0) return;

      // Goldilocks band: both gaps inside [min,max] ATR units
      double sepFM = (dir == 1) ? (f[0] - m[0]) / glkATR : (m[0] - f[0]) / glkATR;
      double sepMS = (dir == 1) ? (m[0] - s[0]) / glkATR : (s[0] - m[0]) / glkATR;
      if(sepFM < InpGlkSepMinATR || sepFM > InpGlkSepMaxATR) return;
      if(sepMS < InpGlkSepMinATR || sepMS > InpGlkSepMaxATR) return;

      // Separation slope persistence
      if(av[InpGlkSlopeLb] > 0)
      {
         double sepNow  = (f[0] - m[0]) / av[0];
         double sepThen = (f[InpGlkSlopeLb] - m[InpGlkSlopeLb]) / av[InpGlkSlopeLb];
         double slope = (dir == 1) ? (sepNow - sepThen) : (sepThen - sepNow);
         if(slope < InpGlkSlopeMin) return;
      }

      g_glkState = 1;
      g_glkDir = dir;
      g_glkArmPrice = c1;
      g_glkPullExtreme = (dir == 1) ? l1 : h1;
      g_glkPullBars = 0;
      g_glkTouch = false;
      return;
   }

   // --- Pullback phase ---
   g_glkPullBars++;
   if(g_glkPullBars > InpGlkMaxPullBars) { GlkReset(); return; }

   if(g_glkDir == 1)
   {
      if(l1 < g_glkPullExtreme) g_glkPullExtreme = l1;
      if(c1 < s[0] - InpGlkInvalATR * glkATR || m[0] < s[0]) { GlkReset(); return; }
      if(l1 <= m[0]) g_glkTouch = true;
      double depth = g_glkArmPrice - g_glkPullExtreme;
      if(g_glkTouch && depth >= InpGlkMinPullATR * glkATR && c1 > o1 && c1 > f[0])
      {
         double sl = g_glkPullExtreme - InpGlkSLBufATR * glkATR;
         double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
         if(entry - sl <= 0 || entry - sl > InpGlkMaxSLATR * glkATR) { GlkReset(); return; }
         if(NativeConfluencePass(1))
            PlaceModuleEntry(1, sl, InpGlkTP_RR, "DX1_G_L", g_magicGLK);
         GlkReset();
      }
   }
   else
   {
      if(h1 > g_glkPullExtreme) g_glkPullExtreme = h1;
      if(c1 > s[0] + InpGlkInvalATR * glkATR || m[0] > s[0]) { GlkReset(); return; }
      if(h1 >= m[0]) g_glkTouch = true;
      double depth = g_glkPullExtreme - g_glkArmPrice;
      if(g_glkTouch && depth >= InpGlkMinPullATR * glkATR && c1 < o1 && c1 < f[0])
      {
         double sl = g_glkPullExtreme + InpGlkSLBufATR * glkATR;
         double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
         if(sl - entry <= 0 || sl - entry > InpGlkMaxSLATR * glkATR) { GlkReset(); return; }
         if(NativeConfluencePass(-1))
            PlaceModuleEntry(-1, sl, InpGlkTP_RR, "DX1_G_S", g_magicGLK);
         GlkReset();
      }
   }
}

//+------------------------------------------------------------------+
//| MODULE H: SESSION VWAP / STRUCTURE PULLBACK CONTINUATION          |
//| Genuine session VWAP: sum(typical_price * tick_volume)/sum(vol)   |
//| accumulated from the Xetra session anchor. Limitation: CFD feed   |
//| provides tick volume only, used as the volume proxy.              |
//+------------------------------------------------------------------+
bool VwapCalc(int excludeLastM1, double &vwap)
{
   if(g_today == 0) return false;
   int startSrvMin = ((InpVwapStartGMT + InpServerUTC) % 24) * 60;
   datetime tStart = g_today + (datetime)(startSrvMin * 60);
   if(TimeCurrent() < tStart + 300) return false;
   int sStart = iBarShift(g_activeSymbol, PERIOD_M1, tStart, false);
   if(sStart < 2 + excludeLastM1) return false;
   double sumPV = 0, sumV = 0;
   for(int sh = 1 + excludeLastM1; sh <= sStart; sh++)
   {
      double h = iHigh(g_activeSymbol, PERIOD_M1, sh);
      double l = iLow(g_activeSymbol, PERIOD_M1, sh);
      double c = iClose(g_activeSymbol, PERIOD_M1, sh);
      if(h <= 0) continue;
      double vol = (double)iVolume(g_activeSymbol, PERIOD_M1, sh);
      if(vol <= 0) vol = 1;
      sumPV += ((h + l + c) / 3.0) * vol;
      sumV  += vol;
   }
   if(sumV <= 0) return false;
   vwap = sumPV / sumV;
   return true;
}

void VwapReset()
{
   g_vwState = 0;
   g_vwDir = 0;
   g_vwPullBars = 0;
   g_vwArmPrice = 0;
   g_vwPullExtreme = 0;
   g_vwTouch = false;
}

double VwapChartATR()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hVwapATR, 0, 1, 2, buf) < 2) return 0;
   return buf[0];
}

void VwapEngine(double atrM1)
{
   static datetime vwLastBar = 0;
   datetime chartBar = iTime(g_activeSymbol, _Period, 0);
   if(chartBar <= 0 || chartBar == vwLastBar) return;
   vwLastBar = chartBar;

   int gmtMin = ContGmtMinOfDay();
   if(gmtMin < InpVwapStartGMT * 60 || gmtMin >= InpVwapEndGMT * 60)
   { if(g_vwState != 0) VwapReset(); return; }

   double atrC = VwapChartATR();
   if(atrC <= 0 || atrC < InpMinATR || atrC > InpMaxATR) return;

   double vwapNow = 0, vwapRef = 0;
   if(!VwapCalc(0, vwapNow)) return;
   if(!VwapCalc(InpVwapSlopeBars, vwapRef)) vwapRef = vwapNow;
   double vwapSlope = vwapNow - vwapRef;

   double c1 = iClose(g_activeSymbol, _Period, 1);
   double o1 = iOpen(g_activeSymbol, _Period, 1);
   double h1 = iHigh(g_activeSymbol, _Period, 1);
   double l1 = iLow(g_activeSymbol, _Period, 1);
   double h2 = iHigh(g_activeSymbol, _Period, 2);
   double l2 = iLow(g_activeSymbol, _Period, 2);

   if(g_vwState == 0)
   {
      int hiIdx = iHighest(g_activeSymbol, _Period, MODE_HIGH, InpVwapStructLb, 2);
      int loIdx = iLowest(g_activeSymbol, _Period, MODE_LOW, InpVwapStructLb, 2);
      if(hiIdx < 0 || loIdx < 0) return;
      double priorHigh = iHigh(g_activeSymbol, _Period, hiIdx);
      double priorLow  = iLow(g_activeSymbol, _Period, loIdx);

      if(c1 > vwapNow && vwapSlope > 0 && c1 > priorHigh)
      {
         g_vwState = 1; g_vwDir = 1;
         g_vwArmPrice = c1; g_vwPullExtreme = l1;
         g_vwPullBars = 0; g_vwTouch = false;
      }
      else if(InpVwapAllowShort && c1 < vwapNow && vwapSlope < 0 && c1 < priorLow)
      {
         g_vwState = 1; g_vwDir = -1;
         g_vwArmPrice = c1; g_vwPullExtreme = h1;
         g_vwPullBars = 0; g_vwTouch = false;
      }
      return;
   }

   // --- Pullback phase ---
   g_vwPullBars++;
   if(g_vwPullBars > InpVwapMaxPullBars) { VwapReset(); return; }

   if(g_vwDir == 1)
   {
      if(l1 < g_vwPullExtreme) g_vwPullExtreme = l1;
      if(g_vwArmPrice - g_vwPullExtreme > InpVwapMaxPullATR * atrC) { VwapReset(); return; }
      if(c1 < vwapNow - InpVwapBreakATR * atrC) { VwapReset(); return; }
      if(l1 <= vwapNow + InpVwapBandATR * atrC) g_vwTouch = true;
      if(g_vwTouch && c1 > o1 && c1 > h2)
      {
         double sl = g_vwPullExtreme - InpVwapSLBufATR * atrC;
         double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
         double stopDist = entry - sl;
         if(stopDist <= 0 || stopDist > InpVwapMaxSLATR * atrC) { VwapReset(); return; }
         double pdh = iHigh(g_activeSymbol, PERIOD_D1, 1);
         if(pdh <= entry || (pdh - entry) < InpVwapMinRoomR * stopDist) { VwapReset(); return; }
         if(NativeConfluencePass(1))
            PlaceModuleEntry(1, sl, InpVwapTP_RR, "DX1_H_L", g_magicVWAP);
         VwapReset();
      }
   }
   else
   {
      if(h1 > g_vwPullExtreme) g_vwPullExtreme = h1;
      if(g_vwPullExtreme - g_vwArmPrice > InpVwapMaxPullATR * atrC) { VwapReset(); return; }
      if(c1 > vwapNow + InpVwapBreakATR * atrC) { VwapReset(); return; }
      if(h1 >= vwapNow - InpVwapBandATR * atrC) g_vwTouch = true;
      if(g_vwTouch && c1 < o1 && c1 < l2)
      {
         double sl = g_vwPullExtreme + InpVwapSLBufATR * atrC;
         double entry = SymbolInfoDouble(g_activeSymbol, SYMBOL_BID);
         double stopDist = sl - entry;
         if(stopDist <= 0 || stopDist > InpVwapMaxSLATR * atrC) { VwapReset(); return; }
         double pdl = iLow(g_activeSymbol, PERIOD_D1, 1);
         if(pdl >= entry || (entry - pdl) < InpVwapMinRoomR * stopDist) { VwapReset(); return; }
         if(NativeConfluencePass(-1))
            PlaceModuleEntry(-1, sl, InpVwapTP_RR, "DX1_H_S", g_magicVWAP);
         VwapReset();
      }
   }
}

//+------------------------------------------------------------------+
//| DASHBOARD                                                         |
//+------------------------------------------------------------------+
void DashUpdate()
{
   if(!InpShowDashboard) return;
   int chartW = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int x = chartW - InpDashX - 320;
   int y = InpDashY;
   int lineH = 18;
   int row = 0;

   DashRect(g_dashPrefix + "BG", x - 10, y - 5, 330, 230, C'20,20,30');
   DashLabel(g_dashPrefix + "H1", x, y + lineH * row, "STRATX | DE40 X1 v2.00",
             clrGold, 10, true); row++;
   DashLabel(g_dashPrefix + "H2", x, y + lineH * row, "8-MOD DAX " + g_activeSymbol,
             clrSilver, 8, false); row++;

   string status = "READY";
   color  stClr  = clrLime;
   if(g_ddPaused)           { status = "PAUSED: DD LIMIT";   stClr = clrRed; }
   else if(g_dayLossPaused) { status = "PAUSED: DAY LOSS";   stClr = clrOrangeRed; }
   else if(g_newsBlackout)  { status = "NEWS BLACKOUT";      stClr = clrYellow; }
   else if(TimeCurrent() - g_attachTime < InpColdStartSec)
                             { status = "COLD START...";      stClr = clrAqua; }
   DashLabel(g_dashPrefix + "ST", x, y + lineH * row, "STATUS: " + status,
             stClr, 9, true); row++;

   DashLabel(g_dashPrefix + "RK", x, y + lineH * row,
             "RISK: " + g_riskName + " " + DoubleToString(g_riskPct, 2) + "%",
             clrSilver, 8, false); row++;

   DashLabel(g_dashPrefix + "TD", x, y + lineH * row,
             "TRADES: " + IntegerToString(g_tradesToday) + "/" + IntegerToString(InpMaxTradesDay) +
             "  LOSSES: " + IntegerToString(g_lossesToday) + "/" +
             (InpStopLossDay > 0 ? IntegerToString(InpStopLossDay) : "OFF"),
             clrSilver, 8, false); row++;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double ddPct = (g_peakEquity > 0) ? (g_peakEquity - equity) / g_peakEquity * 100.0 : 0;
   color ddClr = (ddPct > InpDDCutPct * 0.7) ? clrOrange : clrSilver;
   DashLabel(g_dashPrefix + "DD", x, y + lineH * row,
             "EQ DD: " + DoubleToString(ddPct, 2) + "% / " +
             DoubleToString(InpDDCutPct, 1) + "%",
             ddClr, 8, false); row++;

   if(g_inPosition)
   {
      double cur = (g_tradeDir == 1) ? SymbolInfoDouble(g_activeSymbol, SYMBOL_BID)
                                      : SymbolInfoDouble(g_activeSymbol, SYMBOL_ASK);
      double pR = (g_riskAmount > 0) ?
         ((g_tradeDir == 1) ? (cur - g_entryPrice) / g_riskAmount
                            : (g_entryPrice - cur) / g_riskAmount) : 0;
      color pClr = (pR >= 0) ? clrLime : clrRed;
      DashLabel(g_dashPrefix + "PS", x, y + lineH * row,
                "POS: " + ((g_tradeDir==1)?"LONG":"SHORT") + " @ " +
                DoubleToString(g_entryPrice, _Digits) + " | " +
                DoubleToString(pR, 2) + "R" +
                (g_partialClosed ? " [PARTIAL]" : ""),
                pClr, 8, false); row++;
   }
   else
   {
      DashLabel(g_dashPrefix + "PS", x, y + lineH * row,
                "POS: FLAT", clrGray, 8, false); row++;
   }

   long spread = SymbolInfoInteger(g_activeSymbol, SYMBOL_SPREAD);
   color spClr = (spread > InpMaxSpreadPts) ? clrRed : clrSilver;
   DashLabel(g_dashPrefix + "SP", x, y + lineH * row,
             "SPREAD: " + IntegerToString(spread) + " pts",
             spClr, 8, false); row++;

   if(InpNewsAvoid)
   {
      string nTxt = g_newsBlackout ? ("NEWS: " + g_newsEventName) : "NEWS: CLEAR";
      color  nClr = g_newsBlackout ? clrYellow : clrGray;
      DashLabel(g_dashPrefix + "NW", x, y + lineH * row, nTxt, nClr, 8, false); row++;
   }

   DashLabel(g_dashPrefix + "FD", x, y + lineH * row,
             "FDAX: " + (g_gcRows > 0 ? IntegerToString(g_gcRows) + " rows" : "NO FEED"),
             (g_gcRows > 0) ? clrSilver : clrOrange, 8, false); row++;

   ChartRedraw(0);
}

void DashLabel(string name, int x, int y, string text, color clr, int fontSize, bool bold)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
}

void DashRect(string name, int x, int y, int w, int h, color bgClr)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bgClr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_COLOR, C'40,40,60');
}

void DashCleanup()
{
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, g_dashPrefix) == 0)
         ObjectDelete(0, name);
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| OPTIMISER SCORING (v2.20: hard acceptance bands)                 |
//| User bands: RR floor 0.7; RR0.7->WR80, RR1.0->WR75,              |
//| RR1.5->WR70, RR2.0->WR65; >=21 trades/year per strategy.         |
//| Non-conforming pass -> 0 (GA discards it).                       |
//+------------------------------------------------------------------+
input group "=== Optimiser Scoring ==="
input double InpMinWR          = 0.55;
input int    InpMinTrades      = 30;
input double InpOptYears       = 2.0;   // period length in years (for freq gate)
input double InpOptMinTpy      = 21.0;  // min trades per year (band frequency)

double OnTester()
{
   double profit = TesterStatistics(STAT_PROFIT);
   double dd     = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   double pf     = TesterStatistics(STAT_PROFIT_FACTOR);
   int    trades = (int)TesterStatistics(STAT_TRADES);
   int    wins   = (int)TesterStatistics(STAT_PROFIT_TRADES);
   double grossP = TesterStatistics(STAT_GROSS_PROFIT);
   double grossL = TesterStatistics(STAT_GROSS_LOSS);
   double avgWin = (wins > 0) ? grossP / wins : 0;
   double avgLos = (trades - wins > 0) ? grossL / (trades - wins) : 0;

   // --- hard gates: any miss scores 0 -------------------------------
   if(trades < 10) return 0;
   if(profit <= 0) return 0;
   if(pf < 1.1) return 0;
   if(dd > 15.0) return 0;

   double wr = (double)wins / trades;
   double rr = (avgLos != 0) ? avgWin / MathAbs(avgLos) : 0;
   if(rr < 0.7) return 0;                       // hard RR floor

   double tpy = trades / MathMax(InpOptYears, 0.25);
   if(tpy < InpOptMinTpy) return 0;             // frequency floor

   // --- required WR by band (piecewise linear) ---------------------
   double req;
   if(rr <= 0.7)       req = 0.80;
   else if(rr <= 1.0)  req = 0.80 - (rr - 0.7) * (0.05 / 0.3);
   else if(rr <= 1.5)  req = 0.75 - (rr - 1.0) * (0.05 / 0.5);
   else if(rr <= 2.0)  req = 0.70 - (rr - 1.5) * (0.05 / 0.5);
   else                req = 0.65;
   if(wr < req) return 0;                       // band miss

   // --- score: reward margin, expectancy, frequency, smoothness ----
   double expectancy = profit / trades;
   double freqFactor = MathMin(tpy / 52.0, 2.0);
   double score = expectancy * freqFactor * pf;
   score *= 1.0 + (wr - req) * 4.0;             // WR margin above band
   score *= 1.0 + MathMin(rr - 0.7, 1.3) * 0.5; // RR margin above floor
   if(dd > 6.0) score *= 0.7;
   if(dd > 10.0) score *= 0.6;
   return score;
}
//+------------------------------------------------------------------+