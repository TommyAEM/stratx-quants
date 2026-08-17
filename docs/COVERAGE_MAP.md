# DE40 RESEARCH COVERAGE MAP (phase-2 audit, 2026-08-15)

Ratings: UNEXPLORED / LIGHT / PARTIAL / GOOD / DEEP / EXHAUSTED-WITHIN-DEFINED-SCOPE.
Every "exhausted" claim from phase 1 is restated with its tested scope. Phase-1 MT5 real-tick
configs ≈95; prior DE40_X1 campaign (2026-08-04/05) adds ~243 parsed reports on GER40.s.

| Family | Entry arch tested | Exit arch tested | TF | Dir | Windows | Regimes | Interactions | MT5 tests | Rating | Scope-limited status |
|---|---|---|---|---|---|---|---|---|---|---|
| FBO (X1 A-F) | immediate FBO on 6 levels | FBL partials, fixed 1R | M1/M15 | both | Frankfurt/London/Xetra/USOvlp | EMA200 gate | level x gate GA 8434 | ~150 (X1) | GOOD | TESTED SUBFAMILY EXHAUSTED: immediate-FBO + FBL on M15 with those levels. UNTESTED: retest-entry FBO, structural stops, regime-dependent gates, VWAP-interactive FBO, M30/H1 FBO. |
| ORB | immediate break, hybrid, reversal, fail-rev (ORB-10) | fixed, partials | M5/M15 | both | several anchors | ATR-pct | width veto (XAU only) | ~40 | PARTIAL | TESTED ARCHITECTURES EXHAUSTED for immediate/hybrid ORB. UNTESTED: failed-ORB reversal with displacement Goldilocks, ORB+VWAP extension filter, ORB retest entries, M30 OR. |
| GLK pullback | X1 ModG + SOT intensity gate | fixed 1R/1.2R | M15 | both | 8-16 GMT | sep bands | SOT stack | ~30 | PARTIAL | TESTED VARIANT EXHAUSTED (EMA5/18 percent-gap standalone + SOT stack). UNTESTED: VWAP-Goldilocks, displacement-Goldilocks, range-width-Goldilocks, HTF GLK. |
| VWAP cont | X1 ModH session VWAP pullback | fixed 1.2R | M1/M15 | both | 8-16 | none | structure break | ~20 | LIGHT | TESTED VARIANT EXHAUSTED (continuation). UNTESTED: VWAP extension mean reversion (VWAPX), anchored VWAP, multi-VWAP, VWAP deviation bands, VWAP slope regimes. |
| OBREC | reclaim confirmation | fixed 1R | M15 | both->longs | sessions | EMA200 | none | 6 | LIGHT | TESTED VARIANT EXHAUSTED (impulse-OB + 2-close reclaim). UNTESTED: OB+volume confirm, OB+HTF bias, limit-retrace entries, deeper reclaim bars, M30 OB. |
| EXHREJ | PDH/PDL sweep+wick+volspike | fixed 1R | M15 | both->longs | all-day | none | vol spike | 5 | LIGHT | TESTED VARIANT EXHAUSTED (PD-level + wick + vol). UNTESTED: M30 exhaustion (SHEX), VWAP extension reversion (VWAPX), overnight-range exhaustion, ADX-regime gated exhaustion. |
| XETRA open | 2-bar bias + EMA20 pullback | fixed 1R | M15 | both->longs | 8-10 | EMA200 | none | 2 | LIGHT | TESTED VARIANT EXHAUSTED. UNTESTED: Xetra continuation with displacement Goldilocks, auction-failure reversal, 07-09 DST variant. |
| Asia sweep | sweep+reclaim fade | fixed 1R/Asia edge | M15 | both | 7-10 | none | none | 1 | LIGHT | TESTED VARIANT EXHAUSTED. UNTESTED: sweep+VWAP confluence, sweep depth Goldilocks, London-range failure (LRF), overnight-range variants. |
| BRKRT | close-beyond + retest | fixed 1R | M15 | both->longs | masks | EMA200 | gate ablation | 6 | PARTIAL | TESTED VARIANT EXHAUSTED (60-bar HH/LL + tol 0.4). UNTESTED: BOS/retest on H1 structure, displacement-Goldilocks breakouts, retest-depth surfaces, LVN breakout. |
| SOT port | FVG+B&R full stack | fixed 1R | M15 | both | SOT windows | NATR | H4 confluence | 8 | GOOD | ARCHITECTURE VARIANT EXHAUSTED on MT5 real ticks (2 port gens). Engine-side prior retained. |
| VPPOC | reject+reclaim shallow | POC/1R/fixed variants, friday, tstop | M15 | longs | 7-17 | tag plateau | POC-dist, bucket, days | ~35 | GOOD | CURRENT GENERATION EXHAUSTED for reject-shallow-longs. UNTESTED: deep rejection, VA-width regimes, volume confirm, HTF bias, entry confirmation variants, exit battery (partials/BE/trails), short architecture, profile-session construction, POC migration. |

HIGH-VALUE UNTESTED DOMAINS (phase-2 queue): VWAPX, FORB (failed-ORB reversal), SHEX (M30
short exhaustion), LRF (London range failure), VPPOC exit battery, VPPOC deep-rejection,
displacement/range-width Goldilocks, H1-structure BOS/retest, short-exhaustion alpha,
interaction surfaces (tag x VA%, ext x ATR-pct).
