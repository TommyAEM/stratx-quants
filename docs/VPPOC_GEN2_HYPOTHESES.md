# VPPOC Gen2 — FAILURE FAMILIES + COMPETING HYPOTHESES (2026-08-15)

Evidence: VPPOCF_DEV + VPPOCF_VAL rich ledgers (n=64, 16 losers), tercile analysis.
Matched-winner comparison included per band (same tercile population).

## FAMILY A — mid VA-width weak (n21 WR61.9 net+1.7 vs high WR90.9 net+19.7; losers 8, matched winners 13 with wmfe 0.71)
- H1 transitional profiles: mid-width = developing/trend day where VA edges are not
  rejection zones (price accepts beyond VA). Test: gate VA-width out of [0.787,1.03).
- H2 confound with trend regime: mid-width days coincide with strong H1 trend against fade.
  Test: cross-tab f_h1_bias within mid band (needs n; currently h1_bias degenerate +1 only).
- H3 bucket quantization: mid width = specific bucket counts producing mislocated VAH/VAL.
  Test: bucket-size surface (250 vs 349 vs 450) within mid-width subset.
- H4 noise (n=21). Confidence LOW-MED. Reopen only if gates flip OOS.

## FAMILY B — shallow VWAP distance concentrates losses (13/16 losers at vwap_dist high=0 sentinel)
- H1 no mean-reversion room: entry near VWAP leaves POC target close while stop exposed to noise.
  Test: require |vwap_dist| > 0.5 ATR (new gate; sentinel rows = near-VWAP rows).
- H2 trend-hug regime: price pinned to VWAP from one side = continuation, fade wrong.
  Test: same gate; if gated subset keeps WR on trend days, H2 supported.
- H3 overlap with near-POC entries (poc_dist low is strong though -> partial confound).
- H4 Monday/gap confound (f_gap degenerate 0 in sample -> cannot test; keep gate independent).

## FAMILY C — far-POC entries weak (high band WR63.6 net+6.2 vs low WR85 net+13.6)
- H1 deep fade against drift: far-POC = price far above/below value -> counter-trend depth.
  Test: gate poc_dist < -0.076 for longs (mirror for shorts).
- H2 wide-VA confound with Family A (far POC often mid/high width). Test: gate-Poc-only vs
  gate-VAW-only branches (G2C vs G2B) disambiguate.
- H3 target overshoot: winners wmfe 0.98 reach 1R anyway -> WR problem not target problem;
  supports entry-quality explanation over exit rework.
- H4 noise. Confidence MED.

## FAMILY D — high displacement exhaustion (high disp WR68.2 net+4.5 vs mid WR90.5 net+15.8)
- H1 impulse exhaustion: entering right after large candles = fade into momentum.
  Test: gate disp <= 0.704.
- H2 continuation regime: high disp days trend on.
- H3 ATR-regime confound (disp/ATR normalized; check atr_pct cross-tab: high disp spans all
  atr terciles roughly evenly in sample -> weak confound).
- H4 noise. Confidence MED.

## BRANCH PLAN (competing, independent)
- G2A all three gates (A+C+D)
- G2B VAW gate only
- G2C POC gate only
- G2D DISP gate only
- G2E partial 50%@0.6R
- G2F BE @0.6R+0.05
- G2G ATR trail from 1.0R
- G2H session close 16:59 GMT
Selection: DEV-gold first; any branch improving DEV net R without WR < 65% goes to VAL;
best VAL child vs frozen champion via trade-level diff. DO NOT touch holdout.
