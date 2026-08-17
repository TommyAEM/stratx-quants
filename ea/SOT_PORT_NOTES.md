# SOT Module Port Notes — DE40_SOT_HOST_v0.1

## Scope
`ea/DE40_SOT_HOST_v0.1.mq5` is a fork of `parents/DE40_X1_v2.20_PARENT.mq5`
adding **Module S**: a faithful MQL5 port of the TV-verified **SOT v4.0 GER40**
strategy (`C:\Trading\Terminal-X-V2-Recovered\verified_configs\GER40.json`,
OANDA feed, 51tr / 74.51% WR / PF 3.491 / DD 3.12%, RR 1.0).

Modules A–H are retained for regression. Default mask = S only (128).

## Module bit map (revised)
| bit | value | module |
|-----|-------|--------|
| 0–5 | 1…32 | FBO A–F (unchanged) |
| 6 | 64 | G Goldilocks (unchanged) |
| 7 | 128 | **S SOT v4.0** (new) |
| 8 | 256 | H VWAP (relocated from bit 7 to free bit 7 for S) |

`InpMagic` default changed 446404093 → **4000** (range 4000–4002 per SOT contract).
Magic: SOT/FBO = 4000, GLK = 4001, VWAP = 4002.

> **Bit relocation note:** the parent assigned H (VWAP) to bit 7 (value 128).
> To wire Module S onto bit 7 (value 128) as specified while keeping H
> available, H was moved to bit 8 (value 256). `ModOn(7)` VWAP call-sites in
> `OnInit`/dashboard were updated to `ModOn(VWAP_MODULE_BIT)`.

## UTC → broker-time mapping proof
All session logic runs in GMT via `InpServerUTC` (broker = UTC + InpServerUTC).

| SOT window (UTC) | InpServerUTC=2 (Vantage) | InpServerUTC=3 (PUPrime) |
|------------------|--------------------------|---------------------------|
| Main 15:15–15:30 | 17:15–17:30 | 18:15–18:30 |
| Asia open 10:00–10:15 | 12:00–12:15 | 13:00–13:15 |
| London open 18:30–18:45 | 20:30–20:45 | 21:30–21:45 |
| NY open 10:45–11:00 | 12:45–13:00 | 13:45–14:00 |
| News avoid 12:30–14:00 | 14:30–16:00 | 15:30–17:00 |

## Config keys ported (GER40.json → Module S)
| Config key | Value | Module S input |
|------------|-------|----------------|
| Setup Timeframe | 15 | InpSotTimeframe = PERIOD_M15 |
| Use MA Intensity Filter | true | trend gate always on |
| Intensity Mode | Percent Gap | % gap of (f−s)/s |
| MA Intensity Source | open | iMA PRICE_OPEN |
| Fast EMA Length | 5 | InpSotFastLen |
| Slow EMA Length | 18 | InpSotSlowLen |
| Goldilocks Lower/Upper | 0.026 / 0.66 | InpSotGldLowerPct / UpperPct |
| Goldilocks Duration (bars) | 23 | InpSotGldDuration |
| Smooth MA Intensity | true | InpSotSmoothLen EMA7 (hard-coded on) |
| Intensity Smoothing Length | 7 | InpSotSmoothLen |
| B · Imbalance (FVG) Pullback Entry | true | InpSotUseB |
| D · Break & Retest Entry | true | InpSotUseD |
| D · Pivot Strength | 1 | pivot strength=1 (hard-coded) |
| D · Retest Tolerance (ATR mult) | 2.25 | InpSotDRetestTolATR |
| D · Trigger Mode | Break Of Trigger Candle | close beyond retest trigger bar |
| D · Max Bars After Break | 8 | InpSotDMaxBarsAfterBreak |
| D · Break Detection | Close Beyond | close-beyond break |
| Impulse filter · Break & Retest | true | InpSotDImpFilter |
| Impulse filter · Imbalance | true | always on for B |
| Impulse Body Multiplier | 1.3 | InpSotImpBodyMult |
| Impulse Lookback (bars) | 13 | impulse scan window (hard-coded) |
| Impulse Size x Avg Body | 1.5 | (see note) |
| Average Body Length | 15 | InpSotAvgBodyLen |
| Use Session Filter | true | InpSotUseMain/Asia/Ldn/NY |
| Main Session Window UTC | 1515-1530 | InpSotUseMain |
| Asia Open UTC | 1000-1015 | InpSotUseAsia |
| London Open UTC | 1830-1845 | InpSotUseLdn |
| New York Open UTC | 1045-1100 | InpSotUseNY |
| Asia/London/NY Kill Zone | false | not ported (OFF) |
| Use NATR Regime Guard | true | InpSotNatrGuard |
| NATR Length | 17 | InpSotNatrLen |
| NATR Percentile Lookback | 200 | InpSotNatrLookback |
| NATR Low/High Percentile | 5 / 95 | InpSotNatrLowPct / HighPct |
| Use Day Filter | true | SotDayPass |
| Tuesday | false | Tuesday OFF |
| Enable Manual News Avoidance | true | InpSotNewsAvoid |
| News Window 1 UTC | 1230-1400 | hard-coded 12:30–14:00 |
| ATR Length (SL) | 6 | InpSotATRLen |
| SL Mode | ATR | fixed ATR mode |
| SL ATR Mult | 1.7 | InpSotSL_ATRMult |
| TP Mode | Fixed RR | fixed RR |
| TP Risk:Reward | 1.0 | InpSotTP_RR |
| Hard True RR Mode | true | InpSotHardRR (no BE) |
| Keep BE In True RR Mode | false | no BE (g_sotPosition bypass) |
| Confluence Method / TF / EMA Len | EMA Slope / 240 / 21 | InpSotUseConf, InpSotConfLen, H4 slope |
| Show Dashboard | true | inherited host dashboard |

## Config keys intentionally omitted (display/engine-only, no trade effect)
- All `Show …` / `Plot …` / `Dashboard Position` / `Trade Box …` / `Audit
  Panel …` / `Monthly Table …` / `STRAT-X Bull/Bear` color keys: chart-display
  cosmetics; MT5 uses native CTrade + host dashboard instead.
- `Broker Symbol Suffix (.s)`: replaced by host `DetectDE40Symbol()`.
- `Require Candle Close Confirmation`, `Use 15M/1H/4H/Daily Candle Direction`,
  `Use MA 1/2/3`, `Use MA 1`, `MA 1 Type`, `Use 1M EMA Confirmation`: OFF in
  config — no-ops.
- `A/C/H/O entry modules`: all false in config.
- `Use HTF Bias Filter`, `Use Liquidity Sweep Filter`, `Use Auto-Anchored VWAP
  Filter`, `Use Bar Position Bias Filter`: all false.
- `Use Prior-Day/Week H/L/M Filter`, `Use Candlestick Confirmation` +
  engulfing/pin-bar/displacement sub-flags: false.
- `Backtest Start/End Date`, `Default Qty`, `Margin`, `Close entries rule`,
  `Run mode`, `Alert type`, `risk_free_rate`, `trim_orders`, `calc_range`:
  TradingView engine/test-harness keys — not strategies.
- `Real Swing Pivot Strength (5)`, `Smart Swing Lookback/Buffer (legacy)`:
  legacy SL-mode inputs; Module S uses fixed ATR SL.
- `Min TP Distance (0.5R)`, `Break Even Offset Points (0)`: hard-RR mode makes
  these moot (TP = fixed 1.0R).

## Key implementation decisions / deviations (documented)
1. **Impulse Size x Avg Body = 1.5 (config) vs Impulse Body Multiplier = 1.3.**
   The task spec says "min gap 0.15 ATR per config 'Impulse Size x Avg Body' 1.5
   for imbalance" but that key is *not* the FVG min-gap; it governs a
   size-vs-avg-body extremeness check. The actual FVG min gap on the TV side is
   the parent's `InpMinGapATR`-equivalent (0.15 ATR, hard-coded via
   `InpSotMinGapATR = 0.15`). The impulse body filter uses the explicit config
   value **1.3** (`Impulse Body Multiplier`), which the task also cites
   ("impulse filter body x1.3 vs avg body 15"). Both task-cited values are
   exposed: 1.3 via `InpSotImpBodyMult`, 0.15 via `InpSotMinGapATR`. The `1.5`
   key is omitted because it is not the FVG gap multiplier and conflicts with
   the explicit 1.3 impulse-body multiplier.
2. **FVG mitigation guard** uses "close crossed the zone midpoint" (a
   conservative interpretation of the TV mitigation guard); `InpSotFvgMitGuard`
   toggles it. FVG max age 14 bars (`InpSotFvgMaxAge`), touch entry
   (`InpSotFvgTouch`) per config.
3. **Sunday/Saturday:** the host's global weekend block (Saturday/Sunday return
   in `OnTick`) is preserved as host architecture. OANDA GER40 has a Sunday
   evening session; MT5 DE40 has none, so the config's "Sunday: true" has no
   MT5 counterpart. Tuesday OFF is enforced (`SotDayPass`).
4. **NATR percentile:** computed as `ATR(NATR length) / close * 100` percentile
   over the lookback window (standard NATR), rank position within [5,95].
5. **MFE/MAE cadence:** tracked in `ManagePosition` (host convention, once per
   new M1 bar), consistent with the parent's `g_mfeR` pattern. MAE is added
   (`g_minProfitR`) to satisfy the CSV `MAE_R` column.

## Compile log summary
```
metaeditor64.exe /compile:ea\DE40_SOT_HOST_v0.1.mq5 (PU Prime D0E8209F…)
Result: 0 errors, 0 warnings, cpu='X64 Regular'
```
An earlier intermediate build reported a transient `InpMagic` duplicate /
`InpSL_BufferATR` clobber while editing the Trade-Management input block; both
were repaired before the final clean build. `.ex5` produced (147 KB).