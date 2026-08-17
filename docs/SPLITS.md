# DE40 data splits (locked 2026-08-15, supervisor policy)

MT5 gates use PU Prime GER40.s history; Vantage GER40 for parity/canonical confirmation.

| Split | Range | Tick quality | Purpose |
|---|---|---|---|
| DEV | 2021-01-01 – 2024-12-31 | 2021-22 modeled, 2023-24 ~67% real | discovery + optimisation ONLY |
| DEV-gold | 2023-01-01 – 2024-12-31 | ~67% real ticks | Sobol verification subset |
| VAL | 2025-01-01 – 2025-12-31 | 100% real ticks | primary gate |
| HOLDOUT | 2026-01-01 – present | 100% real ticks | SEALED; Step 24 only; max 3 logged accesses |

Rules:
- Optimiser runs ONLY on DEV. Modeled-tick years never support validation claims.
- VAL seen only after DEV screens pass; VAL failure final for that config id.
- HOLDOUT access logged in docs/HOLDOUT_LOG.md {timestamp, reason, actor}; unlogged = trigger S4.
- Internal WFO folds use rolling windows inside DEV+VAL only.
- Every ledger row records dataset_split + from/to dates.
