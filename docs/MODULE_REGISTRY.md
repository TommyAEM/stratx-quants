# DE40 X1X — MODULE REGISTRY (single-writer, corrected 2026-08-16 v2)

State ladder: SNAPSHOT_FROZEN -> BEST_CURRENT_CHILD -> RESEARCH_ACTIVE ->
PASS_GATES_COMPLETE -> MODULE_ADMITTED. Snapshot-freeze != admission.

TELEMETRY-CORRECTION NOTE: f_disp/f_rel_vol were computed on wrong bars (missing
ArraySetAsSeries on MqlRates) across all harness EAs. FIXED. Any gate keyed on the buggy
f_disp/f_rel_vol is INVALID and must be re-derived from corrected telemetry.

## MODULE 1 — VPPOC (value-area shallow-reject fade -> POC, long) — VALID
- SNAPSHOT_FROZEN = TRUE. BEST_CURRENT_CHILD = FIXED-1R (magic 5003).
- MODULE_RESEARCH_GATE = PASSED: WR 83.3 / PF 5.26 / RR 1.05 / freq 24yr / DD 0.50%.
- UNAFFECTED by the telemetry bug (f_poc_dist / f_va_width are profile-construction features,
  computed from g_poc/g_vah/g_val, not bar-indexed).
- MODULE_1_ACCEPTED_RESEARCH_CANDIDATE = TRUE. Production cert pending (2026 holdout #3,
  InpPocMin plateau, WFO).

## MODULE 2 — VWAPX (VWAP-extension reversion, long) — EDGE INVALIDATED
- SNAPSHOT_FROZEN = TRUE (frozen/DE40_X1X_M2_VWAPX_HIDISP.* preserved for reproducibility).
- The "high-disp (f_disp>=0.80) 61% WR" edge was keyed on the BUGGY f_disp. Corrected:
  f_disp mean ~1.5; disp>=1.0 -> DEV 49.4%/-1.92, VAL 51.9%/+4.57 (marginal, not a gate).
- MODULE_RESEARCH_GATE = NOT PASSED. Raw baseline loss-making (~47-49% WR, PF < 1).
- State: RESEARCH_ACTIVE (edge must be re-derived on corrected telemetry, or family
  deprioritised if no corrected edge survives).

## MODULE 3 — TREND (H1-trend pullback continuation, long) — WEAK
- Baseline 44tr/40.9% (DEV). RR 1.41 via runner (avg win 1.43R) but entry weak + low freq.
- Its "low disp" pocket was also keyed on the buggy f_disp -> re-forens on corrected telemetry
  pending before any gate decision.

## FORB — DEPRIORITISED (regime-flipping gates; marginal raw edge)

## Portfolio state
ONE genuinely validated module (M1). M2/M3/FORB edges are spurious or weak on corrected
telemetry. Module discovery CONTINUES against the portfolio gap (bearish/trend/session-transition).