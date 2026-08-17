# DE40 X1X MODULE 2 (FORB) — BASELINE FORENSICS (2026-08-15)

Baseline: DE40_X1X_M2_FORB v1.00 (magic 4800, source 9f6f0649, ex5 12c4607c).
DEV-gold 2023.09-2024.12, PU Prime GER40.s real ticks, M15, long-only, fixed 1R.
Evidence: evidence/FORBDEV_FORB_BASE_trades.csv (151 trades, full f_* telemetry).

## Baseline result (honest, loss-making)
151 trades / 47.7% WR / PF 0.92 / netR -6.71 / losers 79 / ~113 tr/yr.
Anatomy: 59 stopped (MFE<0.5, entry problem) vs 20 turned (MFE>=0.5, exit); mean loser MFE 0.35.

## Failure families (DEV, cross-checked vs matched winners)
F1 H1-CONTEXT (strongest): h1_bias=+1 (H1 bullish) -> 78tr/41%/-14.13R; h1_bias=-1 (H1 bearish)
   -> 73tr/54.8%/+7.41R. The failed-downside-break long is a counter-H1-DOWNTEND
   exhaustion fade, NOT a trend dip-buy. In an H1 uptrend the downside break is chop/continuation.
F2 MIDDAY CHOP: Midday session (12-15 GMT) -> 25tr/20%/-15.22R (worst bucket). Lunch chop.
F3 AGGRESSIVE RECLAIM: high displacement (disp>=0.4) -> 35tr/37.1%/-9.09R; high rel-vol
   (>=1.3) -> 16tr/31.3%/-6.13R. A big-body/high-volume reclaim is momentum, not a clean fail.
F4 ABOVE-EMA200: f_price_ema200>=0 -> 71tr/40.8%/-12.91R. Fading a downside break above the
   M15 EMA200 is wrong (uptrend pullback, no bottom).

## Positive pockets (edge concentration)
h1_bias=-1 (73/54.8/+7.41) · low-disp (63/58.7/+11.75) · low-relvol (106/52.8/+6.33) ·
high-atr% (85/54.1/+7.52) · below-EMA200 (80/53.8/+6.19) · Wednesday (26/61.5/+6.27) ·
London+USOverlap (121/52/+5.5).

## Combined (combined gates, DEV only — branch candidates, NOT yet validated)
- h1_bias=-1 & disp<0.4            : 32tr/68.8%/+12.64R (10 losers)
- h1_bias=-1 & disp<0.4 & not-Midday: 31tr/71.0%/+13.64R (9 losers)   <- combo_D (best)
- h1_bias=-1 & disp<0.4 & relvol<0.7 & not-Midday: 25tr/72.0%/+11.41R (7 losers)

## Competing hypotheses (to distinguish with branches)
H1: H1 bias is causal regime (downtrend exhaustion) — vs confound with EMA200 distance.
   (DATA: h1_bias alone 54.8%/+7.41 >= h1_bias+below-EMA 54.2%/+5.16 -> EMA200 is mostly
    redundant; h1_bias is the primary regime signal.)
H3: displacement is causal (quiet reclaim = genuine fail) — vs confound with h1_bias.
   (DATA: low-disp alone 58.7%/+11.75 AND h1_bias+low-disp 68.8%/+12.64 -> disp ADDS to h1_bias.)
H2: Midday is causal chop vs confound. (adds a little on top of h1+disp, combo_D 71 vs 68.8.)

## GEN-2 branches (distinguishing mutations — each gate ALONE then combined)
1 FORB_H1      InpGateH1Bear only        (isolate regime)
2 FORB_DISP    InpGateDisp only          (isolate displacement)
3 FORB_H1DISP  h1_bear + disp            (top combo)
4 FORB_H1DISP_MIDDAY h1_bear + disp + excl Midday
5 FORB_H1DISP_RELVOL h1_bear + disp + relvol<=0.7
6 FORB_ALL      h1_bear + disp + relvol + excl Midday
Selection rule: DEV netR improvement without WR<65% -> VAL 2025 trade-level diff vs THIS baseline.

## Next
Implement gates (InpGateH1Bear / InpGateDisp(+InpDispMax) / InpGateRelVol(+InpRelVolMax) /
InpExclMidday) in DE40_X1X_M2_FORB.mq5, compile, run GEN-2 branches on DEV, then VAL.