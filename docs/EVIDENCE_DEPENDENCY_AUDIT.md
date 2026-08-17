# DE40 X1X — EVIDENCE-DEPENDENCY AUDIT

Scope: every artifact under `C:/Trading/DE40-Research` that references telemetry features
`f_disp` or `f_rel_vol`, or that makes a claim keyed on those features.

Root cause (recorded, not re-investigated): `f_disp` and `f_rel_vol` were computed on the
WRONG M15 bars — the harness EAs called `CopyRates(MqlRates, ...)` without
`ArraySetAsSeries(rb, true)` first, so `m15[0]` / `rb[0]` did not refer to the latest bar as
intended. This shifts every recorded `f_disp`/`f_rel_vol` value. The bug is FIXED and the
affected EAs recompiled, but every conclusion drawn from the pre-fix values is suspect until
re-derived.

Auditor role: runtime engineers only. This audit ONLY classifies provenance. It changes no
telemetry, runs no MT5, edits no history, and issues NO rerun decision.

## Classification keys

- `UNAFFECTED`        — claim does not depend on `f_disp`/`f_rel_vol` values (profile-based
                        `f_poc_dist`/`f_va_width`, EMA-based `f_h1_bias`, `f_atr_pct`,
                        `f_price_ema200`, infra, or an already-corrected record).
- `PARTIALLY_AFFECTED`— claim mixes telemetry-independent sub-claims with sub-claims keyed on
                        `f_disp`/`f_rel_vol`.
- `INVALIDATED`       — claim/gate/edge/freeze was keyed on buggy `f_disp`/`f_rel_vol` AND has
                        been pronounced false/spurious on corrected telemetry (M2 VWAPX high-disp).
- `REQUIRES_RERUN`    — claim was keyed on buggy `f_disp`/`f_rel_vol` and the corrected
                        re-derivation is still pending (unknown outcome); not yet known false.

Machine-readable provenance marker for any row that used the buggy feature to make a claim:
the exact line `INVALIDATED_TELEMETRY_INDEXING_BUG` (one per affected row).

---

## Summary count table

| Classification        | Dependents |
|-----------------------|-----------:|
| INVALIDATED           | 6          |
| PARTIALLY_AFFECTED    | 8          |
| REQUIRES_RERUN        | 15         |
| UNAFFECTED            | 19         |
| **Total**             | **48**     |

---

## Section A — affected findings (per-row)

### A.1 INVALIDATED (6)

**A.1.1** `brain/pending_writeback.json` :: `DE40-M2-VWAPX-VAL-PASS`
Claim: "VWAPX high-disp (disp>=0.80) VAL HOLDS 38tr/60.5%/PF1.51/netR+7.92 … ~61% WR across DEV+VAL".
The edge is keyed on buggy `f_disp`; corrected telemetry shows disp>=1.0 -> DEV 49.4% / VAL 51.9% (marginal).
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.1.2** `brain/pending_writeback.json` :: `DE40-M2-FROZEN`
Claim: "VWAPX high-disp frozen as MODULE_2_FROZEN_RESEARCH_CANDIDATE … moderate edge PF1.5".
The freeze decision rests on the invalidated A.1.1 edge.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.1.3** `docs/MODULE_2_VWAPX_FREEZE.md`
Claim: "Gate: require HIGH displacement (f_disp >= 0.80) … STRONG MODULE FOUND / freeze".
Freeze manifest for the invalidated high-disp edge (metrics 31tr/61.3% DEV, 38tr/60.5% VAL).
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.1.4** `checkpoints/CAMPAIGN_STATE.md` :: "MODULE 2 FROZEN — VWAPX HIGH-DISP (2026-08-15)"
Claim: "high-disp gate (f_disp>=0.80) VAL-HOLDS … Module 2 FROZEN: DE40_X1X_M2_VWAPX_HIDISP".
Pre-fix checkpoint recording the now-invalid freeze.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.1.5** `frozen/DE40_X1X_M2_VWAPX_HIDISP.mq5`
Frozen M2 source with `InpGateDisp` gate (require `g_f_disp >= InpDispMin=0.80`). Immutable
snapshot of the invalidated gate (also carried the buggy `CopyRates` indexing).
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.1.6** `frozen/DE40_X1X_M2_VWAPX_HIDISP.set` (also `set/MODULE2_VWAPX_HIDISP.set`, magic 5002)
Frozen gate config `InpGateDisp=true, InpDispMin=0.80` for the invalidated M2 freeze.
INVALIDATED_TELEMETRY_INDEXING_BUG

### A.2 PARTIALLY_AFFECTED (8)

**A.2.1** `brain/pending_writeback.json` :: `DE40-VPPOC-HYP-GATE-POCDISP`
Claim: "GATE (poc-not-mid AND disp-not-high): DEV 19@89.5 … MUST validate".
Correct `f_poc_dist` leg + buggy `f_disp` leg. Later REFUTED by real MT5.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.2** `brain/pending_writeback.json` :: `DE40-M2-FORB-GEN2`
Claim: "baseline … healed to H1DISP_MIDDAY 31tr/71% … DISP causal (58.5% alone), H1-bear compounds,
relvol net-damaging".
Baseline (no gates) and H1-bear (`f_h1_bias`) legs are telemetry-independent; the
"DISP causal" and "relvol net-damaging" legs are keyed on buggy `f_disp`/`f_rel_vol`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.3** `brain/pending_writeback.json` :: `DE40-M2-FORB-VAL-REFUTED`
Claim: "FORB GEN-2 gates OVERFIT … DISP-only PF0.95/-$10 … H1DISP_MIDDAY collapses".
Overfit conclusion is partly independent (H1/Midday also collapsed), but the DISP-only VAL number
is keyed on buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.4** `brain/pending_writeback.json` :: `DE40-M3-TREND-BASELINE`
Claim: "runner delivers RR 1.41 architecturally … edge pockets: shallow pullback (62.5%WR), low
disp (<0.4 -> 50%/+8.19R) …".
Runner-RR and shallow-pullback legs are telemetry-independent; the "low disp" pocket is keyed on
buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.5** `brain/pending_writeback.json` :: `DE40-M3-TREND-WEAK`
Claim: "SHALLOW = 5tr/60%WR/PF1.05 … LOWDISP gate produced 0 trades (inline disp recompute bug;
forensics showed 20 low-disp). CONCLUSION runner delivers RR 1.41 but entry weak+rare".
Shallow-pullback + runner-RR legs independent; the low-disp gate/pocket is keyed on buggy `f_disp`
(the record already self-notes an inline recompute defect on top of the underlying indexing bug).
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.6** `brain/pending_writeback.json` :: `DE40-PORTFOLIO-M1M2-DIVERS`
Claim: "Diversification M1 vs M2 … genuinely diversifying anchors … SHARED long-fade caveat".
M1 leg valid; the M2 (VWAPX high-disp) leg is the invalidated edge, so the diversification
numbers inherit the M2 bug second-order.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.7** `docs/DIVERSIFICATION_M1_M2.md`
Claim: "M1 VPPOC 24 trades. M2 VWAPX high-disp 38 trades … genuinely DISTINCT alpha sources".
Same split: M1 leg UNAFFECTED; M2 "high-disp" leg keyed on buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.2.8** `checkpoints/CAMPAIGN_STATE.md` :: "3. COMPLETED REVIEWS & LESSONS — FORB Campaign"
Claim: "Gen-2 gates: Overfit on DEV (DISP VAL PF 0.95, H1DISP_MIDDAY collapsed)".
Overfit outcome partly independent; the DISP-only VAL figure is keyed on buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

### A.3 REQUIRES_RERUN (15)

**A.3.1** `brain/pending_writeback.json` :: `DE40-VPPOC-FAM-DISP-HIGH`
Claim: "High displacement entries (f_disp>0.704) are weak".
Keyed on buggy `f_disp`. Corrected outcome not yet computed.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.2** `brain/pending_writeback.json` :: `DE40-VPPOC-FAM-RELVOL-HIGH`
Claim: "High relative volume (f_rel_vol>=1.5) entries weak on both splits".
Keyed on buggy `f_rel_vol`. Corrected outcome not yet computed.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.3** `brain/pending_writeback.json` :: `DE40-GEN2-DEV-DISP-REFUTED`
Claim: "DISP gate (f_disp<=0.704) NET-DAMAGING in real MT5 … DISP is a confound/proxy, not causal".
The rejection direction was established on buggy `f_disp` values; must be re-derived on corrected
telemetry before the "DISP rejected" decision on VPPOC can stand.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.4** `brain/pending_writeback.json` :: `DE40-M2-FORB-CAUSAL`
Claim: "DISP is a confound in VPPOC … but CAUSAL in FORB … feature causal role is family-specific".
Both legs keyed on buggy `f_disp`. Corrected causal role unknown.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.5** `docs/FORB_BASELINE_FORENSICS.md`
Claim: "F3 AGGRESSIVE RECLAIM: high displacement (disp>=0.4) -> -9.09R; high rel-vol (>=1.3) ->
-6.13R; positive pockets low-disp (58.7%/+11.75) / low-relvol; combined h1+disp gates; H3
displacement is causal".
The disp/relvol failure families, positive pockets, combined gates and the H3 causal hypothesis are
all keyed on buggy `f_disp`/`f_rel_vol`. (F1 h1_bias, F2 Midday, F4 f_price_ema200 and the
high-atr% / Wednesday pockets in the SAME doc are telemetry-independent — see Section B.)
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.6** `docs/FORB_GEN2_RESULTS.md`
Claim: "DISP gate is the PRIMARY causal gate (58.5%/1.89) … RELVOL gate DAMAGES net (108.63 ->
54.40): rejected … DISP confound in VPPOC but CAUSAL in FORB (cross-family lesson)".
DISP-causal and RELVOL-damaging conclusions are keyed on buggy `f_disp`/`f_rel_vol`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.7** `docs/GEN2_DEV_RESULTS.md`
Claim: "Key finding 2 — DISP forensics projection REFUTED … DISP alone -4.02R, POCxDISP -4.03R …
high-displacement trades include genuine winners (disp=0.81) … DISP is a confound/proxy".
DISP gate ablation on VPPOC was computed on buggy `f_disp` values; needs re-derivation.
(Key findings 1/3/4 — POC gate, VAW gate, exit shaping — do not rely on f_disp/f_rel_vol.)
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.8** `docs/VPPOC_GEN2_HYPOTHESES.md`
Claim: "FAMILY D — high displacement exhaustion (high disp WR68.2 net+4.5 vs mid WR90.5 net+15.8)
… gate disp <= 0.704".
Failure-family bucketing and the DISP gate test keyed on buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.9** `docs/MODULE_2_FORB_BASELINE.md`
Claim: "H2: only SHALLOW breaks fail … displacement/break-depth Goldilocks gate" + telemetry scheme
includes `rel_vol, f_disp`.
The displacement hypothesis and the recorded `f_disp`/`rel_vol` telemetry are keyed on buggy features.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.10** `ea/harness/DE40_X1X_M2_FORB.mq5`
Gate definitions `InpGateDisp` (f_disp<=0.40) and `InpGateRelVol` (f_rel_vol<=0.70). Source now
fixed, but any FORB branch gated on these inputs ran on buggy telemetry.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.11** `ea/harness/DE40_X1X_M3_TREND.mq5`
Gate definition `InpGateLowDisp` (f_disp<=0.40). Source now fixed; the M3 low-disp pocket/gate ran
on buggy telemetry.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.12** `ea/harness/DE40_VPPOC_GEN2.mq5`
Gate definition `InpGateDisp` (f_disp<=0.704) used for the VPPOC DISP branch. (M1's production
freeze keeps `InpGateDisp=false` — the DISP gate is NOT active in the frozen M1 champion.)
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.13** `set/FORB2_DISP.set`, `set/FORB2_H1DISP.set`, `set/FORB2_H1DISP_MIDDAY.set`, `set/FORBVAL_DISP.set`
DISP-gated FORB branch configs (`InpGateDisp=true, InpDispMax=0.40`). Branch results keyed on
buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.14** `set/FORB2_H1DISP_RELVOL.set`, `set/FORB2_ALL.set`
DISP+RELVOL-gated FORB branch configs (`InpGateDisp=true, InpGateRelVol=true`). Branch results
keyed on buggy `f_disp` AND `f_rel_vol`.
INVALIDATED_TELEMETRY_INDEXING_BUG

**A.3.15** `set/M3_LOWDISP.set`, `set/M3_SHALLOW_DISP.set`
M3 low-disp gate configs (`InpGateLowDisp=true, InpDispMax=0.40`). Gate keyed on buggy `f_disp`.
INVALIDATED_TELEMETRY_INDEXING_BUG

---

## Section B — UNAFFECTED (known-correct features / telemetry-independent)

M1 VPPOC gates and all profile-based / EMA-based findings are UNAFFECTED: the bug touched only
`f_disp` (3-bar body / M15 ATR over `MqlRates`) and `f_rel_vol` (tick_volume / 20-bar mean over
`MqlRates`). The known-correct features — `f_poc_dist`, `f_va_width`, `f_h1_bias`, `f_atr_pct`,
`f_price_ema200` — are computed from profile construction, ATR buffers and EMA handles, not from
the mis-indexed `MqlRates` array.

| # | Source | Identifier | Why UNAFFECTED |
|---|---|---|---|
| B.1 | `brain/pending_writeback.json` | `DE40-VPPOC-FAM-POC-MID` | `f_poc_dist` (profile-based) |
| B.2 | `brain/pending_writeback.json` | `DE40-VPPOC-FAM-VAW-LOW` | `f_va_width` (profile-based) |
| B.3 | `brain/pending_writeback.json` | `DE40-VPPOC-FAM-H1-COUNTER` | `f_h1_bias` (EMA-based) |
| B.4 | `brain/pending_writeback.json` | `DE40-GEN2-DEV-POC-GATE` | `f_poc_dist` gate |
| B.5 | `brain/pending_writeback.json` | `DE40-GEN2-DEV-VAW-FREQ` | `f_va_width` gate |
| B.6 | `brain/pending_writeback.json` | `DE40-M1-VPPOC-VAL-PASS` | M1 POC child (profile-gated) |
| B.7 | `brain/pending_writeback.json` | `DE40-M1-FROZEN` | M1 shallow-reject freeze (profile-gated) |
| B.8 | `brain/pending_writeback.json` | `DE40-M1-FIXEDRR-PROMOTE` | M1 fixed-1R RR fix (exit, not telemetry) |
| B.9 | `brain/pending_writeback.json` | `DE40-M2-VWAPX-EDGE-INVALIDATED` | Corrective record (uses corrected telemetry) |
| B.10 | `docs/MODULE_1_VPPOC_FREEZE.md` | M1 VPPOC freeze manifest | `f_poc_dist` gate; DISP/VAW/exit rejected (`f_poc_dist`/`f_va_width`) |
| B.11 | `docs/MODULE_2_VWAPX_SELECTION.md` | VWAPX family selection | Selection on priors; no `f_disp` value claim made |
| B.12 | `docs/COVERAGE_MAP.md` | "displacement/range-width Goldilocks" roadmap | Untested future ideas, no claim on recorded telemetry |
| B.13 | `checkpoints/CAMPAIGN_STATE.md` | "MODULE 1 (VPPOC) FROZEN" | M1 profile-gated champion |
| B.14 | `frozen/DE40_X1X_M1_VPPOC.mq5` (+`.set`) | M1 VPPOC source + config | `InpGateDisp=false`; gate is `InpGatePoc` (`f_poc_dist`) |
| B.15 | `frozen/DE40_X1X_M1_VPPOC_FIXEDRR.mq5` (+`.set`) | M1 fixed-1R champion | `InpGateDisp=false`, `InpGatePoc=true`, `InpFixedRROnly=true` |
| B.16 | `scripts/forensics.py` | `FEATS` tuple + bucketing tool | Analysis tool; the bucketed DISP/RELVOL conclusions it produced are classified in Section A |
| B.17 | `ea/harness/DE40_VPPOC_FORENSIC.mq5` | forensic telemetry logger | Granted: this file LOGS the buggy `f_disp`/`f_rel_vol`; but it is the bug's locus/tooling, not a claim. The claims drawn from its output are in Section A |
| B.18 | `HANDOVER.md` | corrected handover (module table + telemetry-bug note) | Post-fix reconciliation; its M1/M2/M3 statuses ratify the rows above |
| B.19 | `docs/MODULE_REGISTRY.md` | single-writer corrected registry | Post-fix reconciliation: M1 VALID, M2 EDGE INVALIDATED, M3/FORB re-forens pending |

Cross-reference note: `docs/FORB_BASELINE_FORENSICS.md` F1 (`f_h1_bias` counter-H1), F2
(Midday session bucket), F4 (`f_price_ema200` above-EMA200), the high-ATR-pct and Wednesday
pockets, and `docs/FORB_GEN2_RESULTS.md` H1-bear attribution all use known-correct features and
are UNAFFECTED — only their `disp`/`relvol` sub-claims are caught in Section A.

---

## Section C — raw data artifacts (evidence/ *.csv)

The 35 `evidence/*.csv` trade ledgers contain the telemetry columns `f_rel_vol` and `f_disp`
(and `f_range_w`, `f_va_width`, `f_poc_dist`, etc.). These are DATA, not findings, so they are
not bucketed above. Note for provenance:

- The `f_rel_vol`/`f_disp` COLUMN VALUES in every pre-fix ledger are INVALID (mis-indexed).
- The P&L / `R` / `MFE_R` / `MAE_R` / trade-identity columns are UNAFFECTED (real trade sequence).
- Affected VPPOC ledgers (columns `f_rel_vol`,`f_disp`): `VPPOCF_DEV_trades.csv`,
  `VPPOCF_VAL_trades.csv`, `GEN2DEV_GEN2_*.csv` (BASE/DISP/POC/POCDISP/ALLGATES/…),
  `M1FX_M1FX_VAL_trades.csv`, `VAL1_VAL1_POC_trades.csv`.
- Affected FORB ledgers: `FORBDEV_FORB_BASE_trades.csv`, `FORBVAL_FORBVAL_BASE_trades.csv`,
  `FORB2DEV_FORB2_*.csv`, `FORB2VAL_FORB2VAL_*.csv`, `FORBVAL_FORBVAL_DISP_trades.csv`.
- Affected M3/VWAPX ledgers: `M3DEV_M3_*.csv`, `VWAPXDEV_*.csv`, `VWAPXVAL*.csv`,
  `VWAPXPR*/*.csv`, `VWAPXRD*`, `VWAPXRV*`, `VWAPXDEV2*`, `VWAPXVAL2*`.

Any finding recomputed from the `f_disp`/`f_rel_vol` column values in these ledgers must be
re-derived from corrected telemetry (relates to rows in Section A).

---

## Section D — out of scope (not the f_disp / f_rel_vol telemetry feature)

- `ea/DE40_SOT_HOST_v0.1.mq5` — `InpDispBodyATR` ("displacement body min") and
  `InpMaxBarsToDisp` are SOT setup-detection inputs, a DIFFERENT "displacement" concept. Not the
  `f_disp` telemetry feature. Excluded.
- `graphify`/Knowledge-Graph and other non-DE40-Research tooling are outside the research root.

---

## DEFERRED_TO_DEEPSEEK

This audit classifies and tags provenance ONLY. Rerun decisions are out of scope for the auditor
and are hereby deferred. The following findings are candidates whose corrected re-derivation is
pending (no recommendation is made on any of them):

1. `DE40-VPPOC-FAM-DISP-HIGH` (VPPOC high-disp failure family)
2. `DE40-VPPOC-FAM-RELVOL-HIGH` (VPPOC high-relvol failure family)
3. `DE40-GEN2-DEV-DISP-REFUTED` (VPPOC DISP-gate rejection / confound claim)
4. `DE40-VPPOC-HYP-GATE-POCDISP` (poc+disp projection — DISP leg)
5. `DE40-M2-FORB-GEN2` (FORB DISP-causal / relvol-damaging legs)
6. `DE40-M2-FORB-CAUSAL` (DISP causal-role family-specificity)
7. `DE40-M2-FORB-VAL-REFUTED` (FORB DISP-only VAL figure)
8. `DE40-M3-TREND-BASELINE` (M3 low-disp pocket)
9. `DE40-M3-TREND-WEAK` (M3 LOWDISP gate)
10. `DE40-PORTFOLIO-M1M2-DIVERS` (M1-vs-M2 diversification, M2 leg)
11. `docs/FORB_BASELINE_FORENSICS.md` (FORB disp/relvol failure families, pockets, H3)
12. `docs/FORB_GEN2_RESULTS.md` (FORB DISP/RELVOL causal attribution)
13. `docs/GEN2_DEV_RESULTS.md` (VPPOC DISP ablation)
14. `docs/VPPOC_GEN2_HYPOTHESES.md` (VPPOC FAMILY D)
15. `docs/MODULE_2_FORB_BASELINE.md` (FORB H2 displacement hypothesis)
16. `docs/DIVERSIFICATION_M1_M2.md` (M1-vs-M2 diversification, M2 leg)
17. FORB gate configs `set/FORB2_DISP`, `set/FORB2_H1DISP*`, `set/FORB2_ALL`,
    `set/FORBVAL_DISP` (DISP/RELVOL-gated branches)
18. M3 gate configs `set/M3_LOWDISP`, `set/M3_SHALLOW_DISP` (low-disp gate)
19. Harness gate definitions `ea/harness/DE40_X1X_M2_FORB.mq5`,
    `ea/harness/DE40_X1X_M3_TREND.mq5`, `ea/harness/DE40_VPPOC_GEN2.mq5` (DISP/RELVOL inputs)

Zero recommendations. Zero rerun orders. Classification ends here.