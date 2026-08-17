# DE40 X1X MODULE 2 — AUTONOMOUS FAMILY SELECTION (VWAPX)

FORB cycle closed: DEV gates refuted by VAL; raw edge marginal + regime-flipping; deprecated
to weak-diversifier. Module 2 remains OPEN. QUANTS selects the next family itself.

## Candidates + score (0-1 per axis, negative-prior penalty)
| Family | DE40 relevance | Brain prior | Independence from VPPOC | Info value | Neg prior | TOTAL |
|---|---|---|---|---|---|---|
| VWAPX (VWAP-extension reversion) | 0.85 | 0.70 | 0.72 | 0.85 | -0.08 | 3.04 |
| LRF (London-range failure) | 0.70 | 0.55 | 0.80 | 0.70 | -0.20 | 2.55 |
| compression breakout | 0.45 | 0.40 | 0.85 | 0.60 | -0.30 | 2.00 |
| BOS/retest H1 (trend) | 0.50 | 0.45 | 0.90 | 0.60 | -0.35 | 2.10 |

## SELECTED: VWAPX (VWAP-extension mean reversion, long)
Why:
- VWAP is a broad, high-frequency, session-anchored level (resets daily) — a genuinely DIFFERENT
  anchor from VPPOC's multi-day value-area POC; independent failure mode.
- VWAP-extension reversion is a well-established fade archetype with strong cross-market priors
  (NAS100 lesson: VWAP 1.2-1.5 ATR regime significance). DE40 evidence: fades work, continuations
  do not — and only VWAP-CONTINUATION was tested (rejected), NOT VWAP reversion. Untested.
- LRF is niche/session-bounded (lower frequency, prior Asia-sweep rejection). VWAPX outranks it.
- FORB lesson applied: build a CLEAN raw baseline, do NOT over-gate from DEV; VAL is arbiter.

## VWAPX GEN-1 baseline
Anchor: session VWAP (07:00 GMT reset, tick-volume weighted, M15 bars).
Long: completed M15 low extends >= InpVwapExtATR (=1.5) ATR15 BELOW session VWAP, then a
completed M15 bar CLOSES back above the extension line -> LONG. Stop = extension extreme - buffer.
Target fixed 1R. Session 07-17 GMT. Long-only. One position. Full f_* telemetry
(vwap_dist_atr, vwap_ext_atr, price_ema200, atr_pct, rel_vol, disp, h1_bias, hour, weekday,
session). Magic 4700.

Loop: baseline -> forensics -> failure families -> matched winners -> competing hypotheses ->
branches -> VAL arbiter -> freeze/verdict -> next family. NO user confirmation.