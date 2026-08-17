# DE40 X1X — PASS-GATE VECTORS (authoritative)

Two SEPARATE gate objects. Never mix them. A module is not the portfolio.

## 1. MODULE_ACCEPTANCE_GATES (per strategy module)
Around 20 trades/year MINIMUM (NOT 52 — that is a portfolio-level aggregate).

| Dimension | Threshold |
|---|---|
| minimum frequency | >= ~20 trades/year |
| genuine positive edge | positive expectancy on real ticks |
| win rate | >= 70% |
| profit factor | >= 2.0 |
| realised payoff (avg win / avg loss, R) | >= 1.0 |
| max drawdown | < 20% |
| year/regime stability | positive across DEV+VAL |
| parameter robustness | plateau, not a spike |
| validation quality | DEV + VAL on real ticks |
| unique alpha contribution | passes diversification vs admitted modules |

Payoff note: fixed-1R geometry makes PF = WR/(1-WR); with a fixed 1R target, WR>=66.7% is
required to reach PF 2.0, OR a runner/payoff exit decouples PF from WR.

## 2. FINAL_X1X_PORTFOLIO_GATES (the COMBINED master EA)
| Dimension | Threshold |
|---|---|
| total annual trades (combined) | >= 52 |
| overall WR | >= 70% |
| overall PF | >= 2.0 |
| overall realised RR | >= 1.0 |
| combined DD | < 20% |
| regime coverage | bearish/trend + range where evidence supports |
| correlation / collision | no duplicate edges |
| final OOS / WFO / holdout | required |

The portfolio reaches 52+/year by SUMMING specialist modules (e.g. 5 x ~20/yr), never by
forcing one module to generate 52+ alone.

## Module state ladder (separate from gates)
SNAPSHOT_FROZEN -> BEST_CURRENT_CHILD -> RESEARCH_ACTIVE -> PASS_GATES_COMPLETE -> MODULE_ADMITTED.
Snapshot-freeze preserves a version immutably; it does NOT imply module acceptance.