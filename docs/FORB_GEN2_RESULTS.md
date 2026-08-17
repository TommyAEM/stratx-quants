# DE40 X1X MODULE 2 (FORB) — GEN-2 RESULTS (2026-08-15)

Parent (baseline): 151tr/47.7%/PF0.92/netR-6.71/losers79 (GEN-1, no gates).
GEN-2 ex5 hash: 243fe66e (gates added). DEV-gold 2023.09-2024.12, real ticks, long-only.

## GEN-2 branches (distinguishing gates)
| Branch | Trades | WR | PF | Net $ | DD |
|---|---|---|---|---|---|
| H1 alone            | 72 | 54.2% | 1.33 | 67.68  | 0.67% |
| DISP alone          | 65 | 58.5% | 1.89 | 100.37 | 0.49% |
| H1+DISP             | 32 | 68.8% | 3.20 | 108.63 | 0.27% |
| H1+DISP+MIDDAY      | 31 | 71.0% | 3.67 | 114.88 | 0.27% |  <- WINNER
| H1+DISP+RELVOL      | 26 | 69.2% | 2.53 | 54.40  | 0.24% |
| H1+DISP+RELVOL+MIDDAY| 25 | 72.0% | 3.07 | 60.65 | 0.24% |

## Causal attribution (isolated, not stacked blindly)
- DISP gate is the PRIMARY causal gate: disp-only 58.5% WR / PF 1.89 (vs base 47.7%/0.92).
  Low displacement = genuine failed break (quiet reclaim).
- H1-bear (-1) COMPOUNDS it: H1DISP 68.8%/3.20 vs DISP-alone 58.5%/1.89. Regime context.
- Midday-exclusion adds a little: 71%/3.67 vs 68.8%/3.20.
- RELVOL gate DAMAGES net (108.63 -> 54.40): rejected. (removes winners, added on top of disp/h1)

## Winner: FORB2_H1DISP_MIDDAY (locked config)
31 trades / 71.0% WR / PF 3.67 (R-weighted 2.48) / netR 13.57 / DD 0.27% / losers 9.
0 gate violations. Year: 2023 7tr/85.7%/+5.08R; 2024 24tr/66.7%/+8.50R. Both positive.
Frequency ~23/yr (portfolio module, below the 52/yr standalone gate).

## Re-forensics of the child (9 losers)
8 stopped (MFE<0.5), 1 turned (MFE 0.94). No dominant new failure family: scattered across
break_depth/reclaim/disp; 7/9 in London session (but London is net-positive overall). The
obvious next-gates (relvol, deeper break-depth, weekday) are already tested net-damaging or
non-confirmed. Diminishing returns on further DEV gating.

## Cross-family lesson (writeback)
DISP is a CONFLAT confound in VPPOC (fade-to-POC) but a CAUSAL gate in FORB (failed-break
reclaim). The causal role of a feature is family-specific — never transfer a gate between
families without testing.

## Next
VAL 2025 for FORB2_H1DISP_MIDDAY (config locked, fresh magic). If it holds -> freeze as
DE40_X1X_M2_FORB (Module 2 candidate), then diversification test vs M1 before master-EA.