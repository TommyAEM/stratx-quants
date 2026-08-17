# DE40 NEXTGEN — MISSION DEFINITION

Created: 2026-08-15. Owner: StratX LongCat (supervisor reviews at escalation triggers).

## Objective
Build the strongest defensible DE40 (Germany 40 / DAX) MT5 EA via a multi-day autonomous
research campaign. Single exceptionally strong strategy OR multi-strategy EA — evidence decides.

## Canonical environment
- Research terminal: VantageResearch instance (data dir E07A066BDB2C10AD677A715C4DEC32A2,
  `C:\Users\Tommy\AppData\Roaming\VantageResearch\terminal64.exe`), symbols GER40 / GER40ft.
- Live Vantage terminal (PID 8440 at mission start) is Tommy's — NEVER disturb.
- PU Prime terminal (`C:\Program Files\MetaTrader 5`, data D0E8209F..., GER40.s) is the
  data-rich fallback used by the prior campaign; M15 2021-2026, real ticks 2025+, ~67% 2023-24.
- Final evidence: genuine MT5 Strategy Tester real-tick runs (Model=4). Python = forensics/planning/pre-screen only.

## Symbol semantics (verified priors)
- GER40.s: digits 2, point 0.01, spread ~245-310 MT5 points = 2.45-3.10 INDEX points.
- Unit discipline (DJ30 lesson #4): always convert points x _Point to index points before
  any spread/ATR ratio. Never treat raw points as index points.

## Acceptance
- Hard bands (user directive): realized RR >= 0.7; WR per RR (0.7R->80%, 1.0R->75%,
  1.5R->70%, 2.0R->65%); >=21 trades/yr per strategy; >=6 strategies combined.
- Alternate profiles: ~70% WR @ ~1R, or ~65% WR @ ~1.5R, or superior expectancy/PF/DD/robustness.
- No curve-fitting; plateau-validated parameters; DEV/VAL/HOLDOUT splits with logged access;
  WFO + cost/parameter stress before PRODUCTION CANDIDATE label.

## Exhausted families (DO NOT redo without new evidence)
- FBO state machine on 6 structural levels (DE40 X1, 0.6R reversion wall)
- Goldilocks EMA pullback on DE40; session VWAP continuation on DE40
- All 10 opening-range families (ORB-10, MT5 real ticks)
- Wide undirected GA (27 dims, 8434 passes) — use staged funnel + plateau mapping instead

## Structural priors
- DE40 moves travel ~0.6R then revert; exit/horizon mismatch is the core pathology.
- EMA200 / native trend gate = strongest single quality lever; hour/session filters second.
- Validated edges are confluence-based (independent non-price confirmation).
- SOT v4.0 GER40 (TV-verified 51tr/74.51%/PF3.491/DD3.12%) never tested on MT5 DE40 —
  largest untested high-quality prior; port is Gen-1 priority.

## Isolation
- All research in C:\Trading\DE40-Research\. Parents frozen read-only with sha256.
- Never overwrite: XAUUSD X1X customer EA, US30 X1X, DE40_X1_v2.20_PARENT, any production EA.

## Checkpointing
- checkpoints/CAMPAIGN_STATE.md updated at every generation boundary and before any session end.
- evidence/ holds every MT5 report/ledger with provenance; ledger.csv is the config ledger
  (schema in docs/LEDGER_SCHEMA.md).
