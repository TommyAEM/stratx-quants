"""
StratX Master Institutional Alpha & Indicator Toolbox (toolbox.py)
Comprehensive Quantitative & Algorithmic Library:
1. Trend & Directional Movement (ADX, SuperTrend, Ichimoku, EMA/SMA, KAMA, Donchian)
2. Volatility & Range (ATR, Bollinger Bands, Keltner Channels, Choppiness Index, StdDev)
3. Momentum & Oscillators (RSI, MACD, Stochastic, CCI, Williams %R, ROC)
4. Volume & Liquidity (VWAP, OBV, MFI, CMF, Volume Profile LVN/HVN/POC)
5. Smart Money Concepts (SMC) & Price Action (BOS/CHOCH, FVG Imbalance, Mitigation, Order Blocks, Liquidity Sweeps)
6. Macro & Microstructure Confluence (HTF Bias, DXY Inverse Driver, MA Slope, Spread Protection, Session Gates)
"""

from typing import Dict, Any

INDICATOR_TOOLBOX: Dict[str, Dict[str, str]] = {
    # =========================================================================
    # 1. TREND & DIRECTIONAL MOVEMENT
    # =========================================================================
    "ADX (Average Directional Index)": {
        "category": "Trend Strength",
        "use_case": "Trend Strength & Regime Filter",
        "when_to_use": "ADX > 25 indicates strong directional momentum. Block breakout/trend trades when ADX < 20 (ranging market).",
        "mql5_snippet": "int adx_h=iADX(_Symbol,_Period,14); double b[]; ArraySetAsSeries(b,true); CopyBuffer(adx_h,0,0,1,b); double adx=b[0];"
    },
    "SuperTrend": {
        "category": "Trend Direction",
        "use_case": "Dynamic Directional Bias & Trailing Stop",
        "when_to_use": "Use for trailing stops or setting strict bull/bear market state.",
        "mql5_snippet": "int handle = iCustom(_Symbol, _Period, \"SuperTrend\", 10, 3.0);"
    },
    "Parabolic SAR": {
        "category": "Trend Reversal",
        "use_case": "Trend Exhaustion & Stop Out",
        "when_to_use": "Ideal for exit and trailing stop logic. If price touches PSAR, trend continuation probability drops.",
        "mql5_snippet": "int sar_h=iSAR(_Symbol,_Period,0.02,0.2); double b[]; ArraySetAsSeries(b,true); CopyBuffer(sar_h,0,0,1,b); double psar=b[0];"
    },
    "Ichimoku Kinko Hyo": {
        "category": "Multi-dimensional Trend",
        "use_case": "Dynamic Support/Resistance & Trend Envelope",
        "when_to_use": "Price above Kumo Cloud = Strong Bullish. Cloud acts as dynamic support during pullbacks.",
        "mql5_snippet": "int ichi_h=iIchimoku(_Symbol,_Period,9,26,52); double t[],k[]; ArraySetAsSeries(t,true); ArraySetAsSeries(k,true); CopyBuffer(ichi_h,0,0,1,t); CopyBuffer(ichi_h,1,0,1,k); double tenkan=t[0], kijun=k[0];"
    },
    "Moving Average Cross & Alignment (EMA/SMA)": {
        "category": "Baseline Trend",
        "use_case": "Trend Alignment & Crossovers",
        "when_to_use": "Fast EMA (20) > Slow EMA (50) > Baseline (200) confirms institutional trend hierarchy.",
        "mql5_snippet": "int e20=iMA(_Symbol,_Period,20,0,MODE_EMA,PRICE_CLOSE), e50=iMA(_Symbol,_Period,50,0,MODE_EMA,PRICE_CLOSE), e200=iMA(_Symbol,_Period,200,0,MODE_EMA,PRICE_CLOSE); double b20[],b50[],b200[]; ArraySetAsSeries(b20,true); ArraySetAsSeries(b50,true); ArraySetAsSeries(b200,true); CopyBuffer(e20,0,0,1,b20); CopyBuffer(e50,0,0,1,b50); CopyBuffer(e200,0,0,1,b200);"
    },
    "Kaufman Adaptive Moving Average (KAMA)": {
        "category": "Adaptive Trend",
        "use_case": "Noise-Filtered Moving Average",
        "when_to_use": "Adapts sensitivity based on market noise. Speeds up during breakouts and flattens during chop.",
        "mql5_snippet": "int kama_h = iCustom(_Symbol, _Period, \"KAMA\", 10, 2, 30); double b[]; ArraySetAsSeries(b,true); CopyBuffer(kama_h,0,0,1,b); double kama=b[0];"
    },
    "Hull Moving Average (HMA)": {
        "category": "Zero-Lag Trend Direction",
        "use_case": "Smooth, Zero-Lag Directional Bias",
        "when_to_use": "Far superior to standard SMA/EMA for DAX momentum. Use H4 HMA to determine macro regime bias.",
        "mql5_snippet": "int hma_h=iCustom(_Symbol,PERIOD_H4,\"HMA\",20); double b[]; ArraySetAsSeries(b,true); CopyBuffer(hma_h,0,0,2,b); if(b[0]<b[1]) return; // Block BUY when HMA slopes down"
    },
    "Bollinger Band Width (BBW)": {
        "category": "Volatility Expansion",
        "use_case": "Detecting Volatility Squeezes & GARCH Proxy",
        "when_to_use": "BBW breaking 20-period highs indicates volatility explosion. Tight BBW indicates coiling before breakout.",
        "mql5_snippet": "int bb=iBands(_Symbol,_Period,20,0,2.0,PRICE_CLOSE); double up[],lo[]; ArraySetAsSeries(up,true); ArraySetAsSeries(lo,true); CopyBuffer(bb,UPPER_BAND,0,1,up); CopyBuffer(bb,LOWER_BAND,0,1,lo); double bbw=up[0]-lo[0];"
    },
    "Tick Volume Delta": {
        "category": "Order Flow Proxy",
        "use_case": "Candle-Level Institutional Buying vs Selling Pressure",
        "when_to_use": "Comparing tick volume on bullish vs bearish candles over the last 5 bars acts as an order flow delta proxy. Require >55% buy pressure for longs.",
        "mql5_snippet": "long buy_vol=0, sell_vol=0; for(int i=0;i<5;i++){ if(iClose(_Symbol,_Period,i)>=iOpen(_Symbol,_Period,i)) buy_vol+=iVolume(_Symbol,_Period,i); else sell_vol+=iVolume(_Symbol,_Period,i); } double buy_pressure=(double)buy_vol/(buy_vol+sell_vol);"
    },
    "Donchian Channels (BOS)": {
        "category": "Channel Breakout",
        "use_case": "Structural Break of Structure (BOS) & 20-Period Highs/Lows",
        "when_to_use": "Enter long when price breaks above 20-period High. Place SL below 20-period Low.",
        "mql5_snippet": "double donchian_high=iHigh(_Symbol,_Period,iHighest(_Symbol,_Period,MODE_HIGH,20,1)); double donchian_low=iLow(_Symbol,_Period,iLowest(_Symbol,_Period,MODE_LOW,20,1));"
    },

    # =========================================================================
    # 2. VOLATILITY & RANGE
    # =========================================================================
    "ATR (Average True Range)": {
        "category": "Volatility",
        "use_case": "Adaptive Stop Loss Sizing & Volatility Floor",
        "when_to_use": "Scale dynamic SL (SL = 1.5 * ATR). Block entries during dead compression (ATR < 15.0 pts on DE40).",
        "mql5_snippet": "int atr_h=iATR(_Symbol,_Period,14); double b[]; ArraySetAsSeries(b,true); CopyBuffer(atr_h,0,0,1,b); double atr=b[0];"
    },
    "Bollinger Bands": {
        "category": "Volatility Envelope",
        "use_case": "Mean Reversion & Volatility Squeeze Breakouts",
        "when_to_use": "Bandwidth squeeze precedes violent breakout. Price touching 2.5 StdDev band = statistical exhaustion fade.",
        "mql5_snippet": "int bb=iBands(_Symbol,_Period,20,0,2.0,PRICE_CLOSE); double up[],lo[]; ArraySetAsSeries(up,true); ArraySetAsSeries(lo,true); CopyBuffer(bb,UPPER_BAND,0,1,up); CopyBuffer(bb,LOWER_BAND,0,1,lo); double upper_band=up[0], lower_band=lo[0];"
    },
    "Keltner Channels": {
        "category": "Volatility Envelope",
        "use_case": "ATR-Based Volatility Bands",
        "when_to_use": "Superior to Bollinger Bands for filtering noise, as ATR prevents band overexpansion from single spikes.",
        "mql5_snippet": "int handle = iCustom(_Symbol, _Period, \"KeltnerChannels\", 20, 1.5);"
    },
    "Choppiness Index (CHOP)": {
        "category": "Regime Classification",
        "use_case": "Ranging vs Trending State Detection",
        "when_to_use": "CHOP > 61.8 indicates low-liquidity consolidation chop (DO NOT TAKE BREAKOUTS). CHOP < 38.2 confirms explosive trend.",
        "mql5_snippet": "double chop = iCustom(_Symbol, _Period, \"ChoppinessIndex\", 14, 0);"
    },

    # =========================================================================
    # 3. MOMENTUM & OSCILLATORS
    # =========================================================================
    "RSI (Relative Strength Index)": {
        "category": "Momentum Oscillator",
        "use_case": "Overbought/Oversold & Momentum Divergence",
        "when_to_use": "Block longs when RSI(14) > 70 to avoid buying tops. Look for bullish divergence (lower price low + higher RSI low).",
        "mql5_snippet": "int rsi_h=iRSI(_Symbol,_Period,14,PRICE_CLOSE); double b[]; ArraySetAsSeries(b,true); CopyBuffer(rsi_h,0,0,1,b); double rsi=b[0];"
    },
    "MACD (Moving Average Convergence Divergence)": {
        "category": "Momentum Shift",
        "use_case": "Momentum Acceleration & Histogram Shift",
        "when_to_use": "Histogram flipping from negative to positive confirms bullish impulse continuation.",
        "mql5_snippet": "int macd_h=iMACD(_Symbol,_Period,12,26,9,PRICE_CLOSE); double m[],s[]; ArraySetAsSeries(m,true); ArraySetAsSeries(s,true); CopyBuffer(macd_h,0,0,1,m); CopyBuffer(macd_h,1,0,1,s); double macd_main=m[0], macd_sig=s[0];"
    },
    "Stochastic Oscillator": {
        "category": "Range Timing",
        "use_case": "Mean Reversion Precision Timing",
        "when_to_use": "Crossings in oversold (<20) or overbought (>80) zones provide high Sharpe mean-reversion entries in sideways regimes.",
        "mql5_snippet": "int st_h=iStochastic(_Symbol,_Period,5,3,3,MODE_SMA,STO_LOWHIGH); double b[]; ArraySetAsSeries(b,true); CopyBuffer(st_h,0,0,1,b); double stoch=b[0];"
    },
    "CCI (Commodity Channel Index)": {
        "category": "Cyclical Momentum",
        "use_case": "Extreme Statistical Deviation",
        "when_to_use": "CCI > +100 indicates overbought acceleration. CCI < -100 indicates oversold extremes. Fade upon return inside +/-100.",
        "mql5_snippet": "int cci_h=iCCI(_Symbol,_Period,14,PRICE_TYPICAL); double b[]; ArraySetAsSeries(b,true); CopyBuffer(cci_h,0,0,1,b); double cci=b[0];"
    },
    "Williams %R": {
        "category": "Fast Momentum",
        "use_case": "Swing High/Low Exhaustion",
        "when_to_use": "Extremely responsive oscillator. -80 to -100 indicates deep institutional discount zone.",
        "mql5_snippet": "int wpr_h=iWPR(_Symbol,_Period,14); double b[]; ArraySetAsSeries(b,true); CopyBuffer(wpr_h,0,0,1,b); double wpr=b[0];"
    },

    # =========================================================================
    # 4. VOLUME & LIQUIDITY
    # =========================================================================
    "VWAP (Volume Weighted Average Price)": {
        "category": "Institutional Value",
        "use_case": "Institutional Fair Value & Dynamic Anchor",
        "when_to_use": "Institutions use VWAP as fair value benchmark. Price extended > 2 standard deviations from VWAP creates high-expectancy mean reversion.",
        "mql5_snippet": "int vwap_handle = iCustom(_Symbol, _Period, \"VWAP\");"
    },
    "On Balance Volume (OBV)": {
        "category": "Volume Accumulation",
        "use_case": "Institutional Accumulation / Distribution",
        "when_to_use": "If price makes higher highs but OBV fails to make higher highs (bearish divergence), institutional smart money is exiting.",
        "mql5_snippet": "int obv_h=iOBV(_Symbol,_Period,VOLUME_TICK); double b[]; ArraySetAsSeries(b,true); CopyBuffer(obv_h,0,0,1,b); double obv=b[0];"
    },
    "Money Flow Index (MFI)": {
        "category": "Volume-Weighted Momentum",
        "use_case": "Volume-Weighted RSI",
        "when_to_use": "MFI accounts for tick volume alongside price delta, filtering out low-volume false breakouts.",
        "mql5_snippet": "int mfi_h=iMFI(_Symbol,_Period,14,VOLUME_TICK); double b[]; ArraySetAsSeries(b,true); CopyBuffer(mfi_h,0,0,1,b); double mfi=b[0];"
    },
    "Chaikin Money Flow (CMF)": {
        "category": "Institutional Flow",
        "use_case": "Net Buying / Selling Pressure Over Period",
        "when_to_use": "CMF > +0.10 indicates institutional accumulation. CMF < -0.10 indicates heavy distribution.",
        "mql5_snippet": "double cmf = iCustom(_Symbol, _Period, \"ChaikinMoneyFlow\", 20, 0);"
    }
}

INSTITUTIONAL_ALPHA_TOOLBOX: Dict[str, Dict[str, str]] = {
    # =========================================================================
    # 5. SMART MONEY CONCEPTS (SMC) & INSTITUTIONAL PRICE ACTION
    # =========================================================================
    "Break and Retest (BOS & CHOCH)": {
        "category": "Market Structure",
        "use_case": "Trend Continuation & Structural Shift",
        "when_to_use": "Wait for structural Break of Structure (BOS) or Change of Character (CHOCH). Do not chase the break. Place a limit order on the retest of the broken swing level with a tight structural stop.",
        "mql5_logic": "Store swing high/low array. If price closes beyond swing, mark level as Supply/Demand Zone. Place BuyLimit/SellLimit at zone; invalidate if price closes below zone."
    },
    "Fair Value Gap (FVG) & 3-Candle Imbalance": {
        "category": "Institutional Imbalance",
        "use_case": "Rebalancing Entry Target & Inversion Zone",
        "when_to_use": "Bullish FVG: iHigh(...,2) < iLow(...,0) (fvg_bottom=High[2], fvg_top=Low[0]). Bearish FVG: iLow(...,2) > iHigh(...,0) (fvg_bottom=High[0], fvg_top=Low[2]).",
        "mql5_logic": "bool bull_fvg=(iHigh(_Symbol,_Period,2)<iLow(_Symbol,_Period,0)); double fvg_mid=(iHigh(_Symbol,_Period,2)+iLow(_Symbol,_Period,0))/2.0; if(bull_fvg && iLow(_Symbol,_Period,0)<=fvg_mid) OpenBuyPosition();"
    },
    "FVG Staleness & Mitigation": {
        "category": "Imbalance Expiration",
        "use_case": "Cancel Expired / Stale Orders",
        "when_to_use": "Bullish FVG mitigated when Low[curr] <= fvg_top. If not mitigated within 3 bars, mark as STALE.",
        "mql5_logic": "if (bars_since_fvg > 3 && !fvg_mitigated) DeletePendingOrder();"
    },
    "Goldilocks Triple-Confluence Setup": {
        "category": "Multi-Layer Confluence",
        "use_case": "High-Probability Execution",
        "when_to_use": "Enter ONLY when Higher Timeframe (H4) Trend + Lower Timeframe (M5) Market Structure Break + Unmitigated FVG align simultaneously.",
        "mql5_logic": "if (H4_EMA200_Slope > 0 && M5_BOS_Confirmed && PriceWithinPips(FVG_Mid, 10)) ExecuteBuy();"
    },
    "Order Blocks (Institutional Footprint)": {
        "category": "Supply / Demand",
        "use_case": "Origin of Explosive Impulse Move",
        "when_to_use": "Mark the last down-candle before a violent upward displacement that broke structure. The body of this candle acts as strong institutional demand.",
        "mql5_logic": "If displacement bar ATR > 2.5 * AvgATR, store preceding opposing candle (Open to Low). Set BuyLimit at upper boundary of Order Block."
    },
    "Asian & London Session Liquidity Sweeps": {
        "category": "Microstructure Stop Hunt",
        "use_case": "Opening Range Judas Swing Fade",
        "when_to_use": "Mark Asian Session High/Low (22:00-07:00 UTC). If London Open (08:00-09:30 UTC) sweeps Asian High and rapidly closes back inside the range, fade the stop-hunt (enter Short).",
        "mql5_logic": "double asian_high = GetSessionHigh(22, 7); if(iHigh(_Symbol,_Period,1) > asian_high && iClose(_Symbol,_Period,1) < asian_high) OpenSellPosition();"
    },
    "Volume Profile (LVN / HVN / POC)": {
        "category": "Volume Distribution",
        "use_case": "Structural Navigation & Targets",
        "when_to_use": "Price travels rapidly through Low Volume Nodes (LVNs) and stalls at High Volume Nodes (HVNs / Point of Control). Target LVNs and take profit at HVNs.",
        "mql5_logic": "If price enters LVN, ride trend to next HVN. If price approaches HVN, tighten trailing stop to breakeven."
    },

    # =========================================================================
    # 6. MACRO, MULTI-TIMEFRAME & RISK CONFLUENCE
    # =========================================================================
    "HTF Trend Direction (H4/D1 Bias)": {
        "category": "Macro Bias",
        "use_case": "Institutional Directional Gate",
        "when_to_use": "Never take an M5 long if H4 50-EMA is sloping downward. Protects against trading into macro headwinds.",
        "mql5_logic": "int h4=iMA(_Symbol,PERIOD_H4,50,0,MODE_EMA,PRICE_CLOSE); double b[]; ArraySetAsSeries(b,true); CopyBuffer(h4,0,0,2,b); if(b[0]<b[1]) return; // BLOCK_BUYS when H4 EMA50 slopes down"
    },
    "DXY (US Dollar Index) Macro Inversion": {
        "category": "Macro Driver",
        "use_case": "Intermarket Correlation",
        "when_to_use": "DE40 is heavily inversely correlated to the US Dollar Index. If DXY is in a violent bull breakout, block DE40 longs.",
        "mql5_logic": "if (GetSymbolTrend(\"USDX\") == BULLISH_IMPULSE) BlockLongs();"
    },
    "MA Slope & Curvature (Chop vs Momentum)": {
        "category": "Mathematical Slope",
        "use_case": "Trend Health vs Flat Consolidation",
        "when_to_use": "Standard MA crosses lag. Measuring the mathematical derivative/slope: Slope = (EMA[0] - EMA[4])/4. If abs(Slope) < Threshold, regime is flat chop -> BLOCK ENTRIES.",
        "mql5_logic": "int ma=iMA(_Symbol,_Period,20,0,MODE_EMA,PRICE_CLOSE); double b[]; ArraySetAsSeries(b,true); CopyBuffer(ma,0,0,5,b); double slope=(b[0]-b[4])/4.0; if(MathAbs(slope)<1.5) return;"
    },
    "Max Spread Slippage Protection": {
        "category": "Microstructure",
        "use_case": "Liquidity Void Protection",
        "when_to_use": "Block execution if broker spread widens beyond normal baseline (e.g. > 15 points on DE40) during news or market open.",
        "mql5_snippet": "if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > 15) return;"
    },
    "Time Session Gate (Opening Range Timing)": {
        "category": "Session Filter",
        "use_case": "Liquidity & Volatility Timing",
        "when_to_use": "Restrict trade execution exclusively to the liquid Frankfurt/London session (08:30-16:30 UTC) and avoid Friday evening drift.",
        "mql5_snippet": "MqlDateTime dt; TimeToStruct(TimeCurrent(), dt); if(dt.hour < 8 || (dt.hour == 8 && dt.min < 30) || dt.hour >= 17 || (dt.day_of_week == 5 && dt.hour >= 16)) return;"
    },
    "Dynamic Volatility-Adjusted Sizing (ATR Parity)": {
        "category": "Institutional Risk Management",
        "use_case": "Fixed-Fraction Volatility Parity Position Sizing",
        "when_to_use": "Never trade static lots. Scale position size inversely to volatility to enforce constant 1% risk per trade and preserve <5% portfolio drawdown.",
        "mql5_snippet": "double b[]; ArraySetAsSeries(b,true); CopyBuffer(atr_handle,0,0,1,b); double risk_amt=AccountInfoDouble(ACCOUNT_EQUITY)*0.01; double stop_dist=1.5*b[0]; double tick_val=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE); double tick_size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE); double lots=NormalizeDouble(risk_amt/((stop_dist/tick_size)*tick_val),2);"
    },
    "Implementation Shortfall & Slippage Guard": {
        "category": "Execution Algorithms",
        "use_case": "Execution Quality & Slippage Tracking",
        "when_to_use": "Track difference between requested price and broker execution price to monitor broker execution efficiency.",
        "mql5_snippet": "MqlTradeRequest req={0}; MqlTradeResult res={0}; req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.volume=lots; req.type=ORDER_TYPE_BUY; req.price=SymbolInfoDouble(_Symbol,SYMBOL_ASK); req.deviation=10; OrderSend(req, res); double slippage = MathAbs(res.price - req.price);"
    },
    "Daily Drawdown Circuit Breaker": {
        "category": "Capital Preservation",
        "use_case": "Emergency Daily Loss Cutoff",
        "when_to_use": "Instantly halt trading for the day if account equity drops by 3.0% from daily open equity.",
        "mql5_snippet": "static double daily_start_equity=0; MqlDateTime dt; TimeToStruct(TimeCurrent(),dt); if(dt.hour==0 && dt.min==0) daily_start_equity=AccountInfoDouble(ACCOUNT_EQUITY); if(daily_start_equity>0 && AccountInfoDouble(ACCOUNT_EQUITY)<daily_start_equity*0.97) return;"
    },
    "New-Bar Execution Optimizer (CPU & Lag Guard)": {
        "category": "MQL5 Performance Architecture",
        "use_case": "Zero-Lag New-Candle Trigger",
        "when_to_use": "Avoid running heavy multi-indicator loops on every micro-tick. Execute structural entries strictly once per closed/new bar to guarantee backtest realism.",
        "mql5_snippet": "static datetime last_bar_time = 0; datetime cur_bar_time = iTime(_Symbol, _Period, 0); if(cur_bar_time == last_bar_time) return; last_bar_time = cur_bar_time;"
    }
}

def get_toolbox_context() -> str:
    """Returns the complete institutional indicator and alpha toolbox as formatted text."""
    context = "=== 📚 STRATX COMPREHENSIVE INSTITUTIONAL INDICATOR & ALPHA TOOLBOX ===\n\n"
    
    context += "--- SECTION 1: CORE INDICATOR TOOLBOX ---\n"
    for name, data in INDICATOR_TOOLBOX.items():
        context += f"• {name} [{data['category']}]:\n"
        context += f"  - Use Case: {data['use_case']}\n"
        context += f"  - When to Use: {data['when_to_use']}\n"
        context += f"  - Verified MQL5: `{data['mql5_snippet']}`\n\n"

    context += "--- SECTION 2: SMART MONEY CONCEPTS & INSTITUTIONAL ALPHA ---\n"
    for name, data in INSTITUTIONAL_ALPHA_TOOLBOX.items():
        snippet = data.get('mql5_snippet') or data.get('mql5_logic', '')
        context += f"• {name} [{data['category']}]:\n"
        context += f"  - Use Case: {data['use_case']}\n"
        context += f"  - When to Use: {data['when_to_use']}\n"
        context += f"  - Implementation / MQL5: `{snippet}`\n\n"

    context += "--- SECTION 3: 3-TIER CONFLUENCE MATRIX ARCHITECTURE ---\n"
    context += "• Tier 1: Macro & Regime Filter (The Environment):\n"
    context += "  - Choppiness Index (CHOP < 50.0) + H4 HMA Direction (Block counter-trend).\n"
    context += "• Tier 2: Structural Trigger (The Setup):\n"
    context += "  - Donchian Channel BOS (20-period High/Low) OR Asian Session Liquidity Sweep.\n"
    context += "• Tier 3: Execution & Microstructure (The Entry):\n"
    context += "  - VWAP alignment (within 0.25% of VWAP) + 5-Candle Tick Volume Delta (>55% Buy pressure for Longs) + 1.5x ATR Stop.\n\n"

    context += "--- SECTION 4: INSTITUTIONAL RISK & EXECUTION ALGORITHMS ---\n"
    context += "• Dynamic Volatility Parity Sizing: `lots = (Equity * 0.01) / (1.5 * ATR * TickValue)` (Never trade fixed lots).\n"
    context += "• Daily Equity Circuit Breaker: Halt trading if equity drops > 3.0% from day start.\n"
    context += "• Max Spread Void Guard: `if (Spread > 1.0 pts) return;` (Block trading during liquidity voids).\n\n"

    return context
