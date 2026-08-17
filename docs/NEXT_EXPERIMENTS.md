# DE40 NEXTGEN — HIGHEST-VALUE NEXT EXPERIMENTS (ranked)

1. Bear-regime / sample accumulation for VPPOC champion: capture Vantage GER40 real ticks
   from 2026-08 forward (acquire_ticks.py supports GER40) and re-run champion + reclaim on
   the growing 2026 window; target n>=100 before any certification claim. Also run champion
   on 2021-22 modeled ticks as DEV-only bear-regime stress (label modeled).
2. True-volume profile levels: validate tick-volume POC/VAH/VAL against a real-volume feed
   (FDAX or OANDA DE30EUR volume) before promotion.
3. VPPOC reclaim variant optimization: it is the diversifier (VAL 1.01); a small staged
   funnel (tag/SLBuf/VA/lookback) on DEV-gold with VAL gate may lift it to a second member.
4. US-overlap long continuation family: BRKRT USOVLP was DEV-positive/VAL-flat; rebuild with
   VPPOC-style selectivity (ATR-pct regime band from NAS100 lesson) as a third family.
5. Cross-broker parity: run champion on VantageResearch 2026 window once history deepens;
   measure actual Vantage spread/slippage (live check was skipped) and re-lock COST_MODEL.
6. DST handling: replace InpServerUTC constant with DST-aware GMT mapping (reviewer finding 11).

EXHAUSTED — do not redo: SOT MT5 port (2 gens), FBO A-F, ORB x10, GLK pullback, VWAP cont,
OBREC, EXHREJ, XETRA open continuation, Asia sweep reclaim, shorts on 2023-25 regimes.
