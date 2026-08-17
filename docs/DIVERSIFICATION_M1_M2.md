# DE40 X1X — M1 vs M2 DIVERSIFICATION TEST (VAL 2025)

M1 VPPOC (value-area POC fade, long) — 24 trades. M2 VWAPX high-disp (VWAP-extension fade,
long) — 38 trades.

## Result
- Same-day overlap: 3 days (M1 trades 24 distinct days, M2 trades 38 distinct days).
  -> they trigger on DIFFERENT days = different events/anchors. Genuinely diversifying.
- Daily net-R correlation on the 3 shared days: -0.925 (n=3 -> statistically ignorable, but the
  sign is a weak hint of complementarity).
- Entry-hour distributions nearly identical (both cluster 6/9/12/15 GMT -> 07-17 session).

## Verdict
M1 + M2 are genuinely DISTINCT alpha sources (different anchor: multi-day POC vs intraday VWAP;
different trigger: value-area rejection vs VWAP extension; low same-day overlap). NOT "two
versions of the same edge."

SHARED CAVEAT: both are long-only fades in the same session hours. Correlation to market
direction/regime remains: in a sustained downtrend or strong trend regime, BOTH lose (they bet
on mean-reversion up). This is the uncovered portfolio gap.

## Portfolio gap -> Module 3 target
Missing regimes: bearish (short) and trend/momentum (both fades lose in trending markets).
DE40 evidence caveat: shorts net-negative 2023-25, and breakout/trend-continuation families
(SOT/ORB/BRKRT/FBO) were real-tick fragile. So a Module 3 must follow EVIDENCE, not force a
trend module: if no robust non-fade DE40 alpha exists, two complementary fades is the honest
ceiling and the master EA combines M1+M2 with a shared governor.

## Next (autonomous)
Search Module 3 candidates against the "missing regime" gap. If evidence supports a genuine
non-fade/trend or session-transition alpha -> research it; else REJECT-ALL for Module 3 and
proceed to the master-EA governor (combine M1+M2).