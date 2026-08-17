# DE40 NEXTGEN — FINAL REPORT (2026-08-15)

Status: **VALIDATION CANDIDATE (RUNG 1 — single edge)**. Not production. Not a failure:
one genuine, validated, cost-robust edge discovered and frozen; portfolio objective unmet.

## 1. Strategy architecture (surviving)
- **VPPOC_CHAMPION** (module VPPOC, magic 4401): M15 volume-profile shallow-reject,
  longs-only. Profile = prior 4 daily sessions, 349-pt buckets, VA 77%; entry = completed
  M15 bar tags <= 0.08 x D1-ATR beyond VAL and closes back inside VA; SL = tag extreme +
  0.47 ATR(M15); TP fixed 1.0R; session 07-17 GMT; spread guard 400 pts; one position.
  EA: ea/harness/DE40_VPPOC_HARNESS.mq5 (sha ec51297a); config: set/DE40_VPPOC_CHAMPION.set
  (sha a3ccf09a). EX5 deployed to PU Prime Experts.
- Diversifier (research-only, not band-passing): VPPOC reclaim variant (magic 4400,
  set/DE40_VPPOC_RECLAIM.set) DEV PF1.19 / VAL 1.01.

## 2. Research lineage
Baseline harnesses (Gen-1: SOT port, BRKRT, OBREC, EXHREJ, VPPOC) -> forensics
(direction/weekday/hour splits, exit frontiers) -> repairs (longs-only, session masks) ->
Sobol (engine 256pt SOT; MT5 24pt VPPOC/EXHREJ) -> plateau (11 probes) -> VAL gate ->
adversarial review (SEND_BACK_TO_RESEARCH) -> prescribed repairs (tag probes, center-on-VAL,
shorts test, folds) -> champion lock -> holdout (not confirmed) -> Gen-2 families
(XETRA, SWEEP) killed -> final certification.

## 3. Research scale
- Families investigated: 8 (SOT/FBO-regression/BRKRT/OBREC/EXHREJ/VPPOC/XETRA/SWEEP).
- EA generations: 3 (SOT port v1 + 13-fix v2; harness suite + direction-gate patches).
- MT5 real-tick configs evaluated: ~90 (ledger.csv).
- Optimiser: 1 engine Sobol 256pt + 2 MT5 Sobol 24pt + 11 plateau + 4 tag probes + folds.
- Branches rejected: SOT-PORT (exhausted), BRKRT, OBREC, EXHREJ, XETRA, SWEEP.
- Retained: VPPOC champion (validation candidate), VPPOC reclaim (component).
- Reviews: 1 adversarial (trigger 2), 2 supervisor escalations (S1, final), regression tripwire.

## 4. Best performance (VPPOC_CHAMPION, real ticks)
| Split | trades | tr/yr | WR | PF | RR | DD | net R |
|---|---|---|---|---|---|---|---|
| DEV-gold 23.09-24.12 | 34 | 26 | 76.47% | 2.94 | 0.91 | 0.36% | +15.7 |
| VAL 2025 | 30 | 30 | 73.33% | 2.32 | 0.84 | 1.10% | +10.7 |
| HOLDOUT 2026 (logged) | 18 | 31 | 61.11% | 0.85 | 0.54 | 0.91% | -1.3 |
Long/short: longs-only by design (shorts net-negative in every family 2023-25).

## 5. Parameter landscapes
VPPOC tag: 0.05/0.065/0.08/0.10 = 76.0/75.9/76.5/78.4% WR (plateau), 0.14/0.16 cliff
(66.7/64.8). SLBuf 0.35-0.60 positive. Center 0.116 VAL 63.9% vs 0.08 VAL 73.3% ->
boundary adds OOS value (not DEV-specific). EXHREJ: narrow high-selectivity corner only.

## 6. Self-heal report
- Failure families: (a) shorts net-negative everywhere (regime) -> direction split KEEP;
  (b) BRKRT Mon/Fri + 06-09 GMT dead -> session mask; (c) SOT short under-fire 0% WR ->
  spurious H4 confluence gate (root cause: Pine Auto-confluence = transparent on GER40) +
  13 geometry miswires -> repaired; still real-tick-fragile -> branch exhausted;
  (d) EXHREJ VAL frequency collapse -> kill; (e) OBREC VAL negative -> kill.
- Successful repairs: longs-only splits, VPPOC selectivity plateau, tag boundary OOS-validated.
- Failed repairs: SOT port (2 generations), midday session restriction, reclaim-as-champion.
- Structural rewrites: none needed beyond port fidelity; exit architecture fixed at 1.0R
  (frontier-adjudicated honest optimum).
- Learned: bar-model (TV/engine) evidence does not transfer to MT5 real-tick intra-bar fills
  for 1R geometries; direction/session splits dominate DE40 quality; 0.6R wall is not universal.

## 7. Multi-strategy report
Combination policy gate (>=3 VAL band passers) NOT met (1 passer). Portfolio steps 21/23
blocked and documented, not forced. Champion + reclaim diversifier correlation high
(same levels family) — no genuine multi-alpha assembled.

## 8. Robustness
- Folds: 4/4 positive (77.8/75.0/69.2/76.5%). Plateau 10/10 positive. MC 2000 reshuffles:
  max DD ~10R, 0/1000 negative samples. Cost stress 4.10 idx pts/trade: RR 0.81-0.84 >= 0.7.
- HOLDOUT 2026: NOT confirmed (61%/0.85) -> champion capped at VALIDATION CANDIDATE.
- Open risks (reviewer): n=64 combined (Wilson CI 63-84% WR), no bear-regime real ticks,
  tick-volume proxy, cross-broker spread unverified (Vantage native history 2026-08+ only).

## 9. Final EA paths
- MQ5: C:\Trading\DE40-Research\ea\harness\DE40_VPPOC_HARNESS.mq5 (+ XETRA/SWEEP/BRKRT/
  OBREC/EXHREJ harnesses; DE40_SOT_HOST_v0.1.mq5 archived as exhausted branch)
- EX5: PU Prime data D0E8...\MQL5\Experts\DE40_VPPOC_HARNESS.ex5
- SET: C:\Trading\DE40-Research\set\DE40_VPPOC_CHAMPION.set (+ DE40_VPPOC_RECLAIM.set)
- MT5 reports: evidence/RUNS/ (VPPOC_CHAMP_*, VPPOC_TAG_*, VPPOC_PLAT_*, SOT_*, ...)
- Ledgers: evidence/ledger.csv; evidence/*_trades.csv
- Lessons: docs/LESSONS.md (Brain MCP unavailable this session; mirrored to
  C:\Trading\Knowledge-Graph\obsidian-brain\learnings\2026-08-15_DE40_*.md)

## 10. Status
VALIDATION CANDIDATE. RUNG 1. Honest classification: one validated single-strategy edge
with 2026 holdout degradation; portfolio mission unmet; campaign exhaustion NOT claimed —
highest-value remaining areas listed in docs/NEXT_EXPERIMENTS.md.

## 11. Post-certification payoff repair (supervisor-prescribed, 2026-08-15)
FinalCert verdict: FREEZE_CANDIDATE / RUNG 1. Root cause of holdout loss: one ungoverned
weekend-gap trade (-2.63R through the 1R stop); WR drop not significant (z=1.16); failure
is payoff, not entry. Prescribed repairs tested on DEV+VAL (magic 4403/4404):
- V1 POC-distance 0.6R + Friday-flat: DEV 31tr/58.1%/PF1.58; VAL 30tr/73.3%/PF2.62 (+0.21R/tr)
- V2 fixed-1R + Friday-flat: DEV 54.8%/1.31; VAL 73.3%/2.42 -> REVERTED (below champ)
- V3 2-bar time stop: KILL (41.7%/0.82 DEV)
- V4 Friday-flat only: neutral (64.5%/1.67 DEV; 73.3%/2.20 VAL)
- V5 POC-distance only: best VAL (67.7%/2.37 DEV; 73.3%/3.06 VAL, +0.27R/tr)
Prespecified holdout confirmation of V1 (access #2, logged): 14tr/50.0%/PF1.13/+0.4R —
POSITIVE (vs champ -1.3R) but below +20%-of-VAL threshold -> NOT CONFIRMED.
Holdout accesses used: 2 of 3. Champion remains FROZEN as VALIDATION CANDIDATE.
Locked repair config: set/VPPOC_V1_POCDIST.set (sha 593626ad).
