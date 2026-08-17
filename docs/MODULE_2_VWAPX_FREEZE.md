# DE40 X1X — MODULE 2 FREEZE MANIFEST

Module ID: `DE40_X1X_M2_VWAPX_HIDISP`
Status: MODULE_2_FROZEN_RESEARCH_CANDIDATE
Frozen: 2026-08-15

## Edge
Session-VWAP extension mean-reversion (long-only). Price extends >= 1.5 ATR15 BELOW the session
VWAP (07:00 GMT reset), then a completed M15 bar closes back above the extension line -> long.
Gate: require HIGH displacement (f_disp >= 0.80) = impulsive overextension that reverts.
Distinct from M1 (VPPOC): VWAP is an intraday session anchor (daily reset) vs VPPOC's multi-day
value-area POC anchor. Different failure mode, different regime interaction.

## Artifacts (immutable, frozen/)
- Source: `ea/harness/DE40_X1X_M2_VWAPX.mq5`
- Compiled: `DE40_X1X_M2_VWAPX.ex5` (ex5 sha f7c65625...)
- Frozen set: `set/MODULE2_VWAPX_HIDISP.set` (magic 5002)

## Locked config
```
InpServerUTC=3, InpVwapStartGMT=7, InpVwapExtATR=1.5, InpEntryStartGMT=7, InpEntryEndGMT=17,
InpSLBufATR=0.30, InpTP_RR=1.0, InpAllowLong=true, InpAllowShort=false,
InpGateDisp=true, InpDispMin=0.80
```

## Metrics (real ticks)
DEV-gold: high-disp subset 31tr/61.3%/+7.22R (raw baseline 219tr/46.6%/-15.54R).
VAL 2025: 38tr/60.5% WR / PF 1.51 / netR +7.92 / losers 15 / DD 0.33%.
Quarterly 2025: Q1 6/83.3%/+4.03, Q2 11/72.7%/+5.14, Q3 14/42.9%/-2.16, Q4 7/57.1%/+0.91.
Consistent ~61% WR across DEV and VAL (regime-robust — unlike FORB's DEV-VAL flip).
IMPROVED: WR +14pp, netR -15.54 -> +7.92 (VAL), DD 1.57% -> 0.33%.
DAMAGED: frequency 219 -> 38/yr (still ~38/yr on VAL; modest but selective).

## Why this is the causal gate (FORB lesson applied)
Tested the SINGLE causal gate (high displacement) ALONE on VAL — did NOT stack the DEV-derived
session/EMA/ATR filters (which FORB showed overfit). High displacement = impulsive extension.
Rejected clusters: London session (37.5%/-14.4R), deep-below-EMA200 (40.5%/-16.3R), low-disp
chop (43.5%/-36.1R), high-ATR-pct (41.3%/-36.9R).

## Remaining certification gates (non-blockers)
1. 2026 holdout (#3, reserved, prespecified).
2. InpDispMin plateau (0.70/0.80/0.90) robustness.
3. Diversification test vs M1 (VPPOC): overlap / correlation / regime / DD — before master EA.

## Governor directive
VWAPX family (high-disp extension reversion) = STRONG MODULE FOUND (moderate edge) / freeze.
Next: diversification test vs M1, then Module 3 search (portfolio gap).