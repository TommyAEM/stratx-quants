# DE40 X1X — MODULE 1 FREEZE MANIFEST

Module ID: `DE40_X1X_M1_VPPOC_SHALLOW_REJECT`
Status: MODULE_1_FROZEN_RESEARCH_CANDIDATE
Frozen: 2026-08-15

## Edge
Volume-profile shallow-reject fade to POC. Long-only. Mean-reversion within the daily
value area. Excludes entries near POC (|pc_dist| < 0.076 ATR) — the near-POC band has
no mean-reversion room. Earns in rotational/range days; known weakness in trend-acceptance
days. Session: Frankfurt/London/USOverlap (07:00-17:00 GMT).

## Artifacts (immutable)
- EA source: `ea/harness/DE40_VPPOC_GEN2.mq5`
  sha256 `c76c3d05c1f9b42b7f68c3b6dc7d5a71a9db8cb9ab060c1aea506bdeb255d6d1`
- EA compiled: `DE40_VPPOC_GEN2.ex5`
  sha256 `ab1e3668532eaf9c6fc37f276c2393ec950982f606decb7c922c23383bdce7b5`
- Frozen set: `set/MODULE1_VPPOC_SR.set` (magic 5001)
- Frozen snapshot: `frozen/` (read-only copies of the above)

## Locked config (= champion + POC gate only)
```
InpServerUTC=3, InpAllowShort=false, InpAllowLong=true, InpTagATR=0.08,
InpSLBufATR=0.46986, InpVA_Pct=77, InpLookbackDays=4, InpBucketPts=349,
InpGatePoc=true, InpPocMin=0.076  (all other Gen2 inputs off)
```

## Metrics
DEV-gold (2023.09-2024.12, real ticks):
- Module: 29 trades / 82.8% WR / PF 3.93 / netR 16.70 / losers 5
- Parent (champion): 34 / 76.5% / PF 2.91 / netR 15.67 / losers 8

VAL 2025 (real ticks):
- Module: 24 trades / 83.3% WR / PF 3.96 (CSV; 4.51 MT5 USD-weighted) / netR 12.02 / losers 4
- Champion VAL: 30 / 73.3% / PF 2.32 / netR 10.67 / losers 8
- Quarterly 2025: Q1 5/100%/+4.61, Q2 4/100%/+3.60, Q3 10/70%/+1.87, Q4 5/80%/+1.94 (all positive)

IMPROVED: WR +10pp, PF ~2x, netR +1.35 (VAL) / +1.03 (DEV), losers 8->4.
DAMAGED: frequency -5/6 trades (still ~22-26/yr; below the 52/yr family ceiling — pre-existing).

## Parameter plateau
`InpPocMin` plateau (0.05 / 0.076 / 0.10) NOT YET swept. Run before final certification.

## Failure-family research (frozen knowledge)
- Causal weakness: near-POC entries (|poc_dist| < 0.076). Fixed by the gate.
- REJECTED mutations (all net-negative or frequency-damaging): DISP gate, VAW gate,
  POC×DISP, ALLGATES, PARTIAL close, breakeven, ATR trail, session-close.
- Forensics note: the DEV forensics projection of "poc+disp" was REFUTED by real MT5
  (DISP is a confound, not causal) — correlation is not causation.

## Brain lessons
pending_writeback.json records: DE40-VPPOC-FAM-POC-MID, DE40-VPPOC-FAM-DISP-HIGH,
DE40-VPPOC-FAM-VAW-LOW, DE40-VPPOC-HYP-GATE-POCDISP, DE40-VPPOC-LOSER-ANATOMY,
DE40-GEN2-DEV-POC-GATE, DE40-GEN2-DEV-DISP-REFUTED, DE40-GEN2-DEV-VAW-FREQ,
DE40-GEN2-DEV-EXIT-SHAPING, DE40-M1-VPPOC-VAL-PASS, DE40-M1-FROZEN.

## Remaining certification gates (NOT blockers for freeze)
1. 2026 holdout (access #3, reserved) — prespecified locked config before access.
2. InpPocMin plateau (robustness).
3. WFO.
Multiple-testing caveat: threshold 0.076 semi-informed by VAL terciles during discovery,
so VAL is a weaker-than-clean OOS test.

## Governor directive
VPPOC family = STRONG MODULE FOUND / FURTHER MARGINAL RESEARCH DEPRIORITISED
(NOT "strategy space exhausted"). Reopen only if portfolio evidence identifies a
specific weakness. Future VPPOC research must fork a child version; this module is frozen.