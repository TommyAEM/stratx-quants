# DE40 VPPOC Gen2 — DEV-GOLD RESEARCH BATCH RESULTS (2026-08-15)

## Scope
Deep self-healing batch on the frozen VPPOC champion (incumbent). Evidence-directed
branches from failure-family forensics (see VPPOC_GEN2_HYPOTHESES.md + pending_writeback.json).
DEV-gold window 2023.09.01-2024.12.31, PU Prime GER40.s real ticks, M15, long-only.
EA: DE40_VPPOC_GEN2 (compiled 0 errors/0 warnings; compiled from source hash c76c3d05,
.ex5 hash ab1e3668). All runs serial, one terminal at a time.

## Reproducibility anchor
GEN2_BASE (all Gen2 inputs off) reproduced the frozen champion:
34 trades / 76.5% WR / netR 15.67 / PF 2.91 (champion reference: 34tr/76.5%/PF2.94).
The Gen2 window is byte-equivalent to the incumbent.

## Gate regimes (trade CSVs are authoritative — no exit reshaping in these branches)

| Branch | n | WR% | netR | losers | vs BASE netR |
|---|---|---|---|---|---|
| BASE | 34 | 76.5 | 15.67 | 8 | — |
| **POC** | **29** | **82.8** | **16.70** | **5** | **+1.03** |
| DISP | 26 | 76.9 | 11.65 | 6 | -4.02 |
| POCxDISP | 23 | 82.6 | 12.67 | 4 | -3.00 |
| VAW | 11 | 81.8 | 9.18 | 2 | -6.49 |
| ALLGATES | 8 | 75.0 | 6.18 | 2 | -9.49 |

Gate executability verified: 0 violations for POC / DISP / VAW.

## Key finding 1 — POC gate is the only genuine DEV improvement
Remove entries near POC (|f_poc_dist| < 0.076). Result: +1.03R net, WR +6.3pp,
losers 8->5, PF 2.91->3.93.

Trade-level delta BASE->POC: 7 removed trades, net +0.98R (4 wins / 3 losses), all with
poc_dist in [-0.058, +0.002]. The gate removed MORE winners than losers on the surface,
so the net gain is NOT clean loser-removal. The freed slots produced 2 replacement entries
(+2.01R: +1.0R @poc 0.08/disp 0.81, +1.01R @poc 0.084/disp 0.21). Net improvement
15.67->16.70 is therefore sequence-mediated, not a filter effect.

Year stability of POC child: 2023 {8, 87.5%, +4.59R}, 2024 {21, 81.0%, +12.11R}. Both positive.

## Key finding 2 — DISP forensics projection REFUTED
Forensics projected poc+disp as the strongest gate (DEV 19@89.5%). Real MT5 disagrees:
DISP alone is -4.02R net; POCxDISP is -4.03R vs POC alone. High-displacement trades include
genuine winners (the POC replacement +1.0R trade has disp=0.81). DISP is a confound/proxy,
not a causal loser signal. This is the exact "correlation is not causation" trap the
self-healing standard exists to catch.

## Key finding 3 — VAW gate is filter-damage
VAW high-band only (f_va_width >= 1.03): WR 81.8% but frequency 34->11 and net -6.49R.
Removes too many winners. Not viable as a standalone gate.

## Key finding 4 — exit shaping (turned-loser repairs) all net-negative
MT5 report nets vs BASE 202.81 USD:
- PARTIAL 167.77 (WR 85.5% but caps winners at 0.8R avg)
- BE 170.99 (WR drops to 68.6% on breakeven-out trades)
- TRAIL 150.48 (caps winners)
- SESCLOSE 85.76 (WR 60.5%, forces exits before target)
The turned-loser population (MFE>=0.6, 2-3 trades) is too small to pay for exit rework.

> NOTE: trade CSVs under-report changes for exit-shaping branches because LogTradeClose
> records full-position R from original entry to final exit, not the partial/BE/trail
> realized P&L. MT5 report HTML is authoritative for PARTIAL/BE/TRAIL/SESCLOSE economics.

## Child re-forensics (POC branch, 5 surviving losers)
1 winner-turned (MFE 0.61, disp 0.73) and 1 winner-turned (MFE 0.72, deep poc -0.70);
3 stopped (MFE<=0.13) split across low-VAW (0.58/0.78), above-POC (poc +0.34), high-disp (1.47).
No dominant new failure family. The obvious candidate gates (DISP, VAW) are already shown
net-damaging. Remaining losers are heterogeneous -> diminishing returns on further DEV gating.

## Decision
- POC child = IMPROVED (netR +1.03, WR +6.3pp, losers -3) but DAMAGED (frequency -5 trades,
  ~22/yr, already below the 52/yr family ceiling). NOT promoted. Requires VAL 2025 confirmation.
- Multiple-testing caveat: POC threshold (0.076) was semi-informed by VAL terciles during
  discovery, so VAL is a weaker-than-clean OOS test. A clean holdout (#3, reserved) remains.
- INCUMBENT RETAINED. POC held as child branch. DISP/VAW/exit-shaping REJECTED.
- REJECT-ALL for promotion; POC is the only branch advancing to VAL.

## Next research-map gaps (ranked)
1. Run POC child on VAL 2025 (config locked) — the gate to promotion.
2. Robustness plateau: sweep InpPocMin 0.05/0.076/0.10 to confirm threshold stability (not a spike).
3. Above-POC long entries (poc>0) — one POC survivor was +0.34 (entry above POC); small n, untested.
4. Brain flush: pending_writeback.json (now 13 records) -> self_healing_brain.db when Brain MCP returns (flush_pending_writeback.py, idempotent on record_id).