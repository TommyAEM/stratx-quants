# DE40 X1X — MODULE 2 (FORB) BASELINE ARCHITECTURE (BEGIN SELF-HEALING)

Family: FORB — failed opening-range breakout reversal
Module ID (candidate): DE40_X1X_M2_FORB
Magic: 4800    Direction: LONG-ONLY (DE40 23-25 shorts net-negative, transferable lesson)

## Why distinct from Module 1 (VPPOC)
| | M1 VPPOC | M2 FORB |
|---|---|---|
| Anchor | multi-day value-area POC | intraday opening range (daily reset) |
| Trigger | shallow tag-reject beyond VAL (fade to POC) | failed downside OR break (close back above OR_low) |
| Regime | rotational profile days | opening-auction failure days |
| Session | 07-17 GMT (all-day fade) | 08-17 GMT (post-OR) |

## GEN-1 baseline (simplest honest version, to be self-healed)
- Opening range (OR): high/low of completed M15 bars in GMT hours [InpORStartGMT=07, InpOREndGMT=08).
- Long trigger (failed downside breakout): after OR end, a completed M15 bar low < OR_low,
  then a subsequent completed M15 bar CLOSES back ABOVE OR_low. One entry per day.
- Stop: min(M15 low during break, entry) below by InpSLBufATR * ATR(M15).
- Target: fixed InpTP_RR = 1.0R (campaign-standard honest optimum).
- Session gate: entries [InpEntryStartGMT=08, InpEntryEndGMT=17). One position at a time.
- Spread guard, fixed lots, long-only.

## Point-in-time telemetry (for the self-healing loop; f_* style at entry)
module_id, module_name, signal_id, direction, entry_arch="OR-break-fail-reclaim",
stop_arch="break-extreme-buffer", exit_arch="fixed-1R", risk, R, MFE_R, MAE_R,
or_high, or_low, or_width_atr, break_depth_atr, reclaim_bar, gmt_hour, weekday,
session_bucket, price_ema200, atr_pct, rel_vol, f_disp — every trade.

## Competing hypotheses to distinguish after GEN-1 forensics
- H1: failed downside break = trapped shorts -> genuine bullish mean-reversion.
- H2: only SHALLOW breaks fail; deep breaks continue -> displacement/break-depth Goldilocks gate.
- H3: OR width moderates reliability (narrow OR = higher target hit rate).
- H4: time-of-failure matters (early failure vs late-session failure).
- H5: EMA200 trend regime moderates (deeply-below-EMA200 = no bottom).

## Acceptance (module-level, per portfolio standard)
Genuine robust edge; assessed on PF / expectancy / payoff / WR / frequency / DD / year
stability / side stability / parameter+WFO robustness / cost robustness / UNIQUE EDGE.
DIVERSIFICATION TEST vs M1 before master-EA acceptance (overlap, correlation, regime, DD).

## Next concrete step
Implement DE40_X1X_M2_FORB.mq5 + baseline set, compile (0 errors), deploy to PU Prime,
run DEV-gold baseline (2023.09-2024.12) serial, then re-forensics -> failure families ->
competing hypotheses -> mutations.