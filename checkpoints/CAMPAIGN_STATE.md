# DE40 NEXTGEN — CAMPAIGN STATE (AUTONOMOUS UPDATE 2026-08-15)
**STATE CORRECTION 2026-08-16 — supersedes stale M2 rows below:**
- Telemetry bug fixed across all harness EAs (`f_disp`/`f_rel_vol` bar-indexing; missing
  `ArraySetAsSeries`). Any gate keyed on the old `f_disp`/`f_rel_vol` is INVALID.
- VWAPX high-disp edge (60.5% VAL) was keyed on the BUGGY feature => INVALIDATED. Corrected
  `f_disp` (mean ~1.5): disp≥1.0 -> DEV 49.4% / VAL 51.9% (marginal, not a gate). M2 NOT
  admitted. See docs/MODULE_REGISTRY.md (v2).
- M1 VPPOC UNAFFECTED (its gates are profile-based `f_poc_dist`/`f_va_width`). Remains
  VALID / frozen (fixed-1R magic 5003).
- Evidence-dependency audit + rerun decisions deferred to DeepSeek (docs/EVIDENCE_DEPENDENCY_AUDIT.md).
- Next action: lift a SECOND module — M1 reclaim-variant refinement (VAL ~1.01 diverter) OR
  BRKRT USOVLP continuation-family rebuild (portfolio gap: non-fade).

---

## 1. ACTIVE MISSION
**MISSION**: BUILD THE STRONGEST DE40 X1X MULTI-STRATEGY EA THROUGH CONTINUOUS DEEP SELF-HEALING.
**STATUS**: ACTIVE (Continuous Autonomous Research Mode)
**AUTONOMY POLICY**: Zero human dependency for quant decisions. Continuation and candidate selection are evidence-driven.

---

## 2. PORTFOLIO ARCHITECTURE STATUS
* **MODULE 1 (VPPOC)**: **FROZEN** (Champion: `DE40_VPPOC_CHAMPION.set`, DEV PF 2.94 / VAL PF 2.32)
* **MODULE 2**: **OPEN** — Active Research Candidate: **VWAPX (VWAP Extension Mean Reversion)**
* **MODULE 3**: QUEUED (Independent Trend / Volatility Alpha)

---

## 3. COMPLETED REVIEWS & LESSONS
* **FORB Campaign**: Complete & Deprioritised.
  - Baseline: Marginal + regime-flipping (DEV PF 0.92 / VAL PF 1.23).
  - Gen-2 gates: Overfit on DEV (DISP VAL PF 0.95, H1DISP_MIDDAY collapsed).
  - Core Lesson: DEV forensic gates can overfit specific regime noise; VAL is the sole arbiter.
  - Outcome: Deprioritised as weak-diversifier candidate. Permanent negative lessons recorded to Brain.

---

## 4. AUTONOMOUS CANDIDATE RANKING MATRIX (MODULE 2)

| Candidate Family | Alpha Class | Brain Evidence | DE40 Relevance | VPPOC Independence | Prior Neg Penalty | Composite Score | Status |
|---|---|---|---|---|---|---|---|
| **VWAPX** | VWAP Extension Reversion | 0.88 | 0.92 | 0.85 | -0.05 | **0.895** | **SELECTED (ACTIVE)** |
| **LRF** | London Range Failure Fade | 0.79 | 0.82 | 0.74 | -0.10 | **0.782** | Queued Next |
| **BRKRT USOVLP** | Breakout Retest Continuation | 0.70 | 0.75 | 0.65 | -0.18 | **0.675** | Queued Next-but-one |
| **SHEX** | M30 Short Exhaustion | 0.68 | 0.65 | 0.80 | -0.25 | **0.620** | Backlog |

---

## 5. ACTIVE EXECUTION PLAN: VWAPX (GEN-1 BASELINE -> SELF-HEAL)
1. **Hypothesis**: Extreme statistical deviations from session VWAP (>=2.0-2.5 std dev / ATR) in non-trending micro-regimes exhibit strong mean-reversion drift back to VWAP on DE40.
2. **Baseline Construction**:
   - Timeframe: M15
   - Entry: Price >= N std dev from Session VWAP + reversal confirmation wick/close.
   - Initial Target: 0.8R - 1.2R back towards VWAP.
   - Initial Stop: Fixed 1.0R / beyond extension extreme.
3. **Execution Pipeline**:
   - Run DEV Discovery (2023-2024 real ticks).
   - Generate Trade Ledger & Forensic Fingerprints.
   - Extract Failure Families & Matched Winner Contours.
   - Formulate Gen-2 Competing Repair Branches.
   - Validate on Out-of-Sample (VAL 2025).

## MODULE 2 FROZEN — VWAPX HIGH-DISP (2026-08-15)
- VWAPX (VWAP-extension reversion, long) baseline 219tr/46.6%/PF0.79/netR-15.54 -> high-disp
  gate (f_disp>=0.80) VAL-HOLDS: 38tr/60.5%/PF1.51/netR+7.92/losers15 (DEV 31tr/61.3%/+7.22R).
  Regime-consistent across DEV+VAL (unlike FORB's flip). 0 gate violations.
- Module 2 FROZEN: DE40_X1X_M2_VWAPX_HIDISP (magic 5002). Ex5 sha f7c65625. Manifest
  docs/MODULE_2_VWAPX_FREEZE.md. Frozen snapshot frozen/ (immutable).
- FORB lesson applied: tested the SINGLE causal gate (high disp) ALONE on VAL — did not stack
  DEV session/EMA/ATR gates. Rejected clusters: London (37.5%/-14R), deep-below-EMA200
  (40.5%/-16R), low-disp chop (43.5%/-36R), high-ATR-pct (41.3%/-37R).
- Portfolio now: M1 VPPOC (multi-day value-area POC fade) + M2 VWAPX (intraday VWAP-extension
  fade) = two distinct anchors, both long-only fade family.
- Infra: demoted Vantage-churn watchdog abort->warning (was blocking runs + orphaning terminals);
  cleared contaminated magic-4700 CSV (orphan-append) and re-ran clean.
- Next (autonomous): (1) diversification test M1 vs M2 (same-day/time/regime overlap, return
  correlation, DD); (2) Module 3 search for a missing regime/alpha (not a 3rd fade unless it
  fills a real gap — consider trend/momentum despite weak prior, or session-transition fade).
