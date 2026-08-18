# EDGE → PASS PLAYBOOK — StratX DE40 Quant Desk
**Written:** 2026-08-18 · **For:** any agent (kimi-k3 desk, or future runs) driving StratX from zero to a passed strategy
**Grounded in:** `Research-Library/.../DISCOVERY_PLAYBOOK`, `DISCOVERY_LESSONS_LEARNED`, `Terminal-X/FOREX_OPTIMIZATION_PLAYBOOK` (the July forex passes), and the measured DE40 work in this repo (`evidence/edge_screen.json`, `evidence/prototype_grid_X1X_M1_PDC.json`)
**Rule zero:** every gate number lives in `AUTHORITATIVE_GATES` (`orchestrator/stratx_live_console.py`). No second source of truth. No gate-shopping.

---

## What "good" looks like — the arithmetic building block

The canonical module gate is **WR ≥ 70% AND PF ≥ 2.00 AND realised RR ≥ 1.00 AND ≥ 20 trades/yr AND MaxDD ≤ 6%**, then walk-forward + independent review + governor.

PF = (WR × avgWin) / ((1−WR) × avgLoss). So there are exactly **two families** of passing strategies:

| Family | Profile | Arithmetic |
|---|---|---|
| **A. High-WR** | WR ≥ 70%, RR ≥ 1.0 | 0.70 × 1.0 / 0.30 = PF 2.33 ✓ |
| **B. High-RR** | WR ≥ 35%, RR ≥ 3.8 | 0.35 × 3.8 / 0.65 = PF 2.05 ✓ |

**Anything between these families with neither axis is dead on arrival.** A WR 31.6% / PF 0.90 / RR < 1 population (what the loop ground all night) has NO lever to pull — healing cannot double WR and triple PF simultaneously. Kill it (STAGE 3 kill gate) and move on. This is the July lesson `LOW-BASE-QUALITY`: base WR <45% tops out in the 50s. EXHAUSTED. Do not polish turds.

Expectancy floor: after costs (≈0.08R/trade on DE40 M15), a strategy needs **≥ +0.10R/trade** to survive the physical-test haircut. Below that, no exit geometry saves it.

---

## STAGE 0 — DISCOVERY (find the measured anomaly)

**Owner:** `orchestrator/edge_discovery.py` · **Cost:** seconds · **Burn:** zero MT5

1. Run the deterministic screen over the full real dataset (28,213 M15 bars, 2023.09–2024.12): session edge map, Asia fakeout ×3 clock hypotheses, prior-day H/L sweep, Frankfurt momentum.
2. Every screen reports occurrences, win fraction, mean ATR-normalised forward move, exact binomial p-value, BH-FDR flag. **Only trust n ≥ 100.**
3. **Micro-window refinement** (July lesson 13 — Tommy's US30 method): the winning structure lives in 15–30-minute pockets, not broad session blocks. Sweep micro-windows *within* active hours before concluding a session has no edge. Broad blocks dilute pockets with noise.
4. **Direction check:** a strongly NEGATIVE reversal drift IS a positive continuation signal (PDC was found this way: sweep-reversal −0.40 ATR, n=991 → continuation +0.40 ATR).
5. Record everything to the Brain — a measured NON-edge is as valuable as an edge (it stops future loops from rebuilding dead theses).

**Pass to STAGE 1:** any anomaly with n ≥ 100 and |mean_fwd_atr| ≥ 0.05 (materiality floor). **Kill:** everything else. No intuition theses.

## STAGE 1 — PROTOTYPE (cheap truth before any EA)

**Owner:** `orchestrator/prototype_lab.py` · **Cost:** ~30s for ~900 variants · **Burn:** zero MT5

1. Simulate the hypothesis directly on the bars: signal → entry at next bar open → SL/TP walk with **stop-first conservatism** → R per trade, costs included, one position at a time, daily loss breaker.
2. Run the full parameter grid (stop × RR × displacement × session × loss-cap). This is the landscape map **without burning MT5**.
3. **Viable region bar:** n ≥ 100 AND PF ≥ 1.30 AND expectancy ≥ +0.05R. No viable cell → **SHELVE the thesis with zero MT5 compute burned.** This is what a cheap kill looks like.
4. **Near-miss refinement** (July lesson 1): if the best cell is close (PF 1.2–1.3), run a FINE pass around it before shelving — coarse grids step over real passes.
5. **Seed, don't guess:** the viable cell becomes the EA's default inputs (`apply_params_to_code`). Measured defaults, not intuition.
6. **DD arithmetic before any code:** prototype maxDD in R × risk% per trade must fit the 6% canonical ceiling. PDC example: 14.4R × 0.4% = 5.8% ✓. If the R-DD can't fit any sane risk, shelve.

**Measured reference (PDC grid, real bars):** best cell stop 1.0 ATR / RR 3.0 / disp 0.50 / 8–12 GMT → N=206, WR 34.5%, PF 1.42, +0.30R, payoff 2.70, maxDD 14.4R, 154 trades/yr. Note: PF 1.42 < 2.00 — the prototype says PDC is a *tradeable* edge but NOT yet canonical; STAGE 3 healing must close that gap with confluence, not geometry.

## STAGE 2 — PHYSICAL SEED (one EA, right the first time)

1. Generate the EA from the thesis template **with seeded defaults**. Run `find_impossible_breakout_triggers` on the code — a Donchian/BOS channel that includes the signal bar (start shift 1) can never fire (close ≤ high always); this bug burned a whole night on Module_5. Start channels at shift 2.
2. MetaEditor compile must be **0 errors** — the compile-fix loop repairs, it doesn't design.
3. ONE physical MT5 run. Parse real metrics (N, WR, PF, RR, DD, consec losses). This number is the thesis's birth certificate.

**Kill check:** if the physical result is hopeless (`is_hopeless_thesis`: PF < 1.00 on N ≥ 20, or WR < 50% AND RR < 1.0), the thesis is dead **now**, not after 35 iterations.

## STAGE 3 — SELF-HEAL (bounded, evidence-led, with a hall of fame)

The loop: full-population forensics → losing clusters → matched winners → causal hypotheses → ONE targeted repair → physical MT5 → keep/revert on delta → memory commit → repeat **under the same self-review goal**.

Hard rules (all enforced in code — do not bypass):
- **RR < 1.0R = auto-reject.** Winners must pay at least what losers cost. No incumbency, no debate.
- **Kill gate:** best population hopeless after 2 evaluations or a landscape map → thesis killed, Brain records why, advance. The Historian must not re-nominate killed theses without NEW measured evidence.
- **Reforensics block:** a review routing CHILD_REFORENSICS_REQUIRED forbids the next mutation until fresh child forensics actually exist.
- **No repair recipes:** forced directives name the measured diagnosis (population collapse / DD tail / payoff floor / loss clustering / weak edge) — never the solution.
- **Tommy-loop discipline** (July playbook 3d): micro-revisit convergence with keep-if-improves floors; when converged, 2–4 random jabs to open new avenues; dry spells **backtrack to the hall of fame** (top-5 distinct incumbents); never "done" until budget exhausted.
- **Plateau ≠ exhaustion** (July lesson 2/7): a thesis may be declared exhausted only after ≥ 5 documented restarts from genuinely different regions, each logging what the last plateau taught.

**Building on winners:** every incumbent update, kill, and landscape map is Brain-committed with metrics. The Historian's job is to nominate from what MEASURED WELL — not to rediscover dead ends.

## STAGE 4 — VALIDATION (trust nothing that selected itself)

1. **Anchored walk-forward** (3 expanding IS/OOS window pairs): pass = ≥2/3 windows with OOS PF ≥ 0.8× IS PF, OOS trades ≥ 3, no catastrophic window (PF < 0.5).
2. **Reproducibility re-run** (July lesson 4): re-run the candidate independently; divergence > ±1% on WR/PF/DD/trades = REPRODUCIBILITY_FAILED. "Verified" has previously meant "the settings never applied".
3. **Select-on-OOS inflation** (July lesson 8): any loop that consulted OOS in its accept rule reports an optimistic OOS. The final number is the one-shot held-out test, never the loop's own read. Quote OOS, never the train/full-window number.

## STAGE 5 — ACCEPTANCE & PORTFOLIO

1. Canonical gates (single authority) → self-review exit gatekeeper → **independent reviewer** (adversarial, re-verifies from raw evidence) → **governor** → admit/freeze. Rejection reopens the SAME goal.
2. **RESEARCH INCUMBENT ≠ ACCEPTED.** An improving child may hold the baseline while failing gates; nothing displays as accepted until every gate passes.
3. Portfolio assembly: 5 accepted modules, combined annual trades ≥ 100, **combined MaxDD < 10%** at 1% risk with 1 concurrent position, verified on the synthesized master EA. Modules that individually pass but combine into DD breach = portfolio FAIL, swap the worst correlation contributor.

---

## Failure taxonomy (log every death against these — saves future dead ends)

| Tag | Signature | Action |
|---|---|---|
| `FREQUENCY-STARVED` | can't reach ~20 trades/yr at any loosening | entry model doesn't fire — EXHAUSTED unless data grows |
| `LOW-BASE-QUALITY` | base WR <45%, pockets sparse | tops out in the 50s — EXHAUSTED, kill early |
| `HOPELESS-PROFILE` | PF < 1.0 on N≥20, or WR<50% & RR<1.0 | kill gate fires — no healing |
| `PAYOFF-PATHOLOGY` | high WR but RR < 1.0 (74%/0.41R class) | exit geometry forbidden — rebuild exits, fixed RR target |
| `BROAD-NO-POCKETS` | flat hour map, no micro-windows | only random jabs help — long budget or kill |
| `PHANTOM-PASS` | great train, collapses OOS | select-on-OOS inflation — one-shot OOS is the verdict |
| `DEAD-TEMPLATE` | 0 trades through the whole repair ladder | run the trigger linter — structural code bug, not a market problem |

## Current DE40 book (measured, 2026-08-18)

| Thesis | Evidence | Status |
|---|---|---|
| X1X_M1_PDC (prior-day sweep continuation) | screen +0.40 ATR n=991; prototype PF 1.42 +0.30R | **STAGE 2 seeded** — heal toward PF 2.0 |
| X1X_M1_FBO (Asia fakeout fade) | screen ~zero edge (n=1765, +0.005 ATR) | measured NON-edge — do not rebuild without new evidence |
| Module_5 DonchianBOS | impossible trigger (fixed); rebuilt variant PF 0.90 N=155 | hopeless profile — killed by gate |
| Module_3 ZScore chop-fade | N=58, WR 41%, PF 1.40, DD 3.5% | live population, below floor — healable candidate |
| Module_4 OpeningGap | N=8, WR 87.5%, PF 3.57 | tiny sample mirage — needs frequency work before any claim |

*The funnel's job: many anomalies in → few prototypes → fewer EAs → rare acceptance. Every stage kills cheap what the next stage would kill expensively.*
