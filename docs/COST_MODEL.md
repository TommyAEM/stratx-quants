# DE40 (GER40.s) COST MODEL — LOCKED

Status: **LOCKED — hard-coded default for ALL tester runs**.
Locked: 2026-08-15 by InfraManifest (DE40 NEXTGEN wave 1, step 4).
Scope: every MT5 real-tick (Model=4) run and every pre-screen accounting in this campaign.
Any change to these numbers requires a doc update + supervisor sign-off; changing them
invalidates comparisons with earlier tester runs.

## Unit discipline (DJ30 lesson #4)

- GER40.s: **digits 2, point = 0.01 index point** (verified prior: MISSION.md symbol semantics).
- **1 index point = 100 MT5 points.**
- ALWAYS convert raw MT5 points × point (0.01) to index points before any spread/ATR/R ratio.
  Never treat raw MT5 points as index points.

## Locked cost numbers

| Component | Locked value | Basis |
|---|---|---|
| Worst-case spread | **310 MT5 points = 3.10 index points** | prior verified live spread band 245–310 MT5 pts (MISSION.md); worst case locked |
| Spread floor (informational) | 245 MT5 points = 2.45 index points | same prior source |
| Slippage per fill (entry or exit) | **0.50 index points** | **ASSUMPTION** — never measured live in this campaign |
| Round-trip cost per trade | **4.10 index points** | spread 3.10 + 2 × 0.50 slippage (one fill per side), worst-case lock |

Round-trip decomposition: the full spread is paid across entry+exit (half-spread each side);
slippage is assumed on every fill → total = spread + 2 × slippage = 3.10 + 1.00 = **4.10 index pts**.

## Measured live spread

**Not measured.** The optional identity/live check was skipped
(`docs/data_manifest.json` → `live_check.status = "skipped"`: MetaTrader5 python package not
installed; no terminal was launched). The worst-case lock above therefore remains the operative
number. If a later live check measures actual spread, this document MUST be updated and the
numbers re-locked before any further tester comparisons.

## M15 ATR sample

**Not measured** (live check skipped). Prior assumption, labeled **ASSUMPTION**:
**DE40 M15 ATR ≈ 30–80 index points.** Central value **55** used for headline figures;
sensitivity table covers the full 30/55/80 range.

## Cost per trade in R (SL width = k × M15 ATR)

Formula:

```
cost_R = round_trip_cost_index_pts / (ATR_index_pts × k)
       = 4.10 / (ATR × k)
```

| SL width (k × ATR) | ATR = 30 | ATR = 55 | ATR = 80 |
|---|---|---|---|
| **1.7 × ATR** | 0.0804 R | 0.0439 R | 0.0301 R |
| **2.0 × ATR** | 0.0683 R | 0.0373 R | 0.0256 R |
| **2.5 × ATR** | 0.0547 R | 0.0298 R | 0.0205 R |
| **3.0 × ATR** | 0.0456 R | 0.0248 R | 0.0171 R |

Worst case in the table ≈ **0.080 R** per trade (tightest 1.7 × 30-ATR stop at worst-case
4.10 index-pt cost). At central ATR 55: 0.024–0.044 R depending on stop width.

## Enforcement

- These numbers are the **hard-coded default for every tester run**: total cost
  **4.10 index points** is deducted per closed trade (equivalently `cost_R` from the table
  keyed off the module's actual SL width).
- Modules report gross R (per-trade CSV, parent convention); the cost deduction is applied in
  accounting/ledger post-trade.
- No per-run overrides. Spread/slippage/ATR anomalies during a run (e.g. live measured spread
  > 3.10) are recorded in evidence but do not change the locked default without this doc being
  revised and re-locked.

## Evidence file

Hashes, sizes, mtimes, tick-quality flags and live-check record: `docs/data_manifest.json`.
