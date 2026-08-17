# Experiment ledger schema (evidence/ledger.csv)

One row per evaluated config (backtest, optimiser cell, or pre-screen).

Columns:
config_id,parent_config,hypothesis_id,symbol,terminal,feed,module,generation,search_method,
parameters_json,dataset_split,from_date,to_date,modelling,trades,trades_per_year,wins,wr_pct,
realized_rr,pf,dd_pct,net_r,expectancy_r,max_consec_loss,longs_trades,longs_wr,shorts_trades,
shorts_wr,retention_vs_parent_pct,removed_losers,removed_winners,new_losers,new_winners,
verdict,reason,evidence_path,timestamp

Verdicts: PASS | NEAR_PASS | KEEP | MODIFY | REVERT | RETAIN_AS_COMPONENT | RETAIN_AS_FILTER |
RETAIN_AS_TRIGGER | EXHAUSTED | REJECTED

search_method values: STAGED | SOBOL | LHS | ANNEALING | GENETIC | EXHAUSTIVE | COORDINATE |
MANUAL_HYPOTHESIS | ARCHITECTURAL_MUTATION | PLATEAU_PROBE

Rules:
- Every MT5 run writes its report + trade ledger to evidence/<config_id>/ before the ledger row.
- HOLDOUT rows must carry holdout_access=true and a logged reason (docs/HOLDOUT_LOG.md).
- A config is never labelled PASS on DEV alone; promotion requires VAL then holdout/WFO per ladder.
