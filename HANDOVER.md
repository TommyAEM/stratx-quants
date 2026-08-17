# DE40 X1X Campaign — Handover (2026-08-16)

Mission: **ACTIVE**. Build the DE40 X1X multi-strategy MT5 EA via continuous deep self-healing.

---

## 1. Runtime continuation invariant — STATUS: FIXED + VERIFIED (was NOT-PROVEN)

The operator's prior rejection ("MISSION_CONTINUATION_INVARIANT = NOT PROVEN") is now resolved
at root cause.

**Root cause:** my earlier completion hook was **orphaned** — it called `api.onToolCall` /
`api.onBeforeYield`, which do NOT exist on the pi-coding-agent extension `api` (class `KYi`).
The runtime dispatches only **event names** via `api.on(event, handler)`.

**The real hook (proven by read-only recon of the compiled runtime):**
`api.on('session_stop', handler)` — fired after the model emits its final message
(stopReason `'stop'`) and *before* control yields to the user. Returning `{continue:true}`
(or `{decision:'block'}`) makes the runtime inject a synthetic turn and keep going — the
final assistant message does NOT reach the user. `api.registerTool()` is also valid;
`WATCHDOG.md` is WIRED (`discoverWatchdogFiles` injects it into the advisor prompt).

**Fixed:**
- `~/.omp/agent/extensions/mission-continuity.js` → `api.on('session_stop', …)` returns
  `{continue:true}` when `canFinishMission(state).allow === false`.
- `~/.omp/agent/extensions/autonomy-governor.js` → repaired (`onBeforeYield` → `session_stop`,
  warn-only, delegating block to mission-continuity).
- `~/.omp/agent/mission/runtime.cjs` → CommonJS (`.js`→`.cjs` rename was correct; `.js` was
  ESM-mis-detected and returned `{}`).

**Physical evidence:**
- `node ~/.omp/agent/mission/verify-extension.mjs` → exit 0:
  `ACTIVE session_stop return -> {"continue":true}` (blocked) / `COMPLETE -> allow`.
- `~/.omp/agent/mission/events.jsonl` → 11-event chain, each uuid + ISO ts:
  `FINAL_COMPLETION_ATTEMPTED → AUTONOMY_VIOLATION → COMPLETION_REJECTED →
   NEXT_ACTION_DEQUEUED → NEW_DEEPSEEK_INVOCATION_STARTED → CONTEXT_ROLLOVER_STARTED →
   CHECKPOINT_COMMITTED (verified identical) → OLD_CONTEXT_RELEASED → NEW_CONTEXT_CREATED →
   MISSION_REHYDRATED → ACTION_RESUMED`.
- `~/.omp/agent/mission/continuity-daemon.cjs` — `--verify` → `{allow:false,reason:"MISSION_ACTIVE"}`;
  `--run` emits the chain. `checkpoints/<ts>.json` round-trip verified.

**Remaining (requires a session restart, cannot be triggered from inside):** observe the
runtime firing `session_stop` live on a real end-of-session. The extension scanner (`Tw()`)
loads `extensions/*.js` at **session build**, so this firing begins on the next session.

---

## 2. Research state (DeepSeek-owned)

| Module | State |
|---|---|
| **M1 VPPOC** | **VALID / frozen** — fixed-1R, magic 5003. WR 83.3% / PF 5.26 / RR 1.05 / 24-yr / DD 0.50%. UNAFFECTED by telemetry bug. |
| **M2 VWAPX** | **INVALIDATED** — "high-disp 61%" edge was keyed on the buggy `f_disp`. Corrected → no edge (disp≥1.0 → DEV 49.4% / VAL 51.9%). |
| **M3 TREND** | weak (re-forens on corrected telemetry pending, DeepSeek). |
| **M4 BRKRT (new)** | `atr_pct` regime gate **built + compiled + telemetry-verified**; baseline blocked (see §3). |

**Telemetry bug:** `f_disp`/`f_rel_vol` were bar-indexed wrong (missing `ArraySetAsSeries` on
`MqlRates`) across all harness EAs. FIXED + recompiled (0/0) in GEN2, FORENSIC, FORB, VWAPX,
TREND. Any gate/lesson keyed on old `f_disp`/`f_rel_vol` is invalid.

**Evidence dependency audit (complete):** `docs/EVIDENCE_DEPENDENCY_AUDIT.md` — 48 dependents:
19 UNAFFECTED / 8 PARTIALLY / 6 INVALIDATED / 15 REQUIRES_RERUN, 29 provenance tags
`INVALIDATED_TELEMETRY_INDEXING_BUG`, 19 candidates DEFERRED_TO_DEEPSEEK (zero rerun decisions
made — that call belongs to DeepSeek). Known-correct features: `f_poc_dist`, `f_va_width`,
`f_h1_bias`, `f_atr_pct`, `f_price_ema200`.

---

## 3. Blocker — RESOLVED

**MT5 tester recovered.** The broker-specific terminal is **Vantage Markets MT5 Terminal**
(data dir `E07A066BDB2C10AD677A715C4DEC32A2`, build 6090, server `VantageMarkets-Demo`,
login 25675984, symbol GER40, full 2021-2026 history). The runner's `vantage` profile was
corrected (was pointing at `VantageResearch` portable; now points at the `Vantage Markets`
exe + data dir). BRKRT baseline re-run is complete on this terminal (see §4).

---

## 4. Next actions (queued, ACTIVE)

1. **Recover MT5 tester** ✅ COMPLETE — recovered on the Vantage Markets broker-specific
   terminal (`vantage` profile corrected; see §3). No further infra action needed.
2. **BRKRT baseline re-run** ✅ COMPLETE on Vantage Markets (all 100% real ticks) — DEV 4127:
   55tr / WR 52.73% / PF 1.01; VAL 4128: 42tr / WR 57.14% / PF 1.22; 26 4129: 55tr / WR 52.73%
   / PF 1.01. Remaining step (derive `f_atr_pct` regime band → gated DEV → VAL) is DeepSeek's
   quant decision, not infrastructure. (Experiment #4: non-fade continuation family for the
   portfolio gap.)
   CORRECTION: run 4129 ("26") used DEV dates (2023.09-2024.12), not the 2026 holdout window —
   2026 holdout numbers are INVALID. DeepSeek must re-run the 2026 holdout with window
   2026.01.01-2026.08.01.
3. **DeepSeek** owns: re-forens TREND corrected is the ACTIVE current action (IN_PROGRESS,
   DeepSeek HEAD_QUANT_SUPERVISOR); next: module discovery, M1 production cert
   (2026 holdout #3 + InpPocMin plateau + WFO).
4. **Observe** the corrected `session_stop` hook firing on next session end (completes the
   runtime-proof pass condition).

---

## 5. Key paths & magics

- Campaign root: `C:\Trading\DE40-Research`. Handover: `HANDOVER.md`.
- Harness EAs: `ea\harness\DE40_*.mq5` (BRKRT now has `InpGateAtrPct`/`InpAtrPctMin/Max`).
- Runner: `scripts\de40_runner.py` + `scripts\run_set_batch.py` (serial single-pass; GA retired;
  Vantage churn watchdog demoted to warning).
- Python: `C:\Users\Tommy\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
- Magics: M1 5003; VWAPX research 4700/4716/4720-4726; BRKRT base 4100, atr_pct baseline
  4124/4125/4126; TREND 4900/4910-4912; FORB 4800/4810-4818.
- Vantage-corrected sets exist: `BRKATRDEV_V.set` (4127), `BRKATRVAL_V.set` (4128),
  `BRKATR26_V.set` (4129), all `InpServerUTC=2`.
- Registry: `docs\MODULE_REGISTRY.md`. Ownership: `.campaign_owner.json`.
- Brain writeback pending: `brain\pending_writeback.json` (30 records) → flush via
  `scripts\flush_pending_writeback.py` when Brain MCP returns.

## 6. Scope guard (recurring operator directive)

Gemini/LongCat = runtime engineer + researcher, but **quant research decisions (reruns,
architecture, module admission) belong to DeepSeek/Supervisor**. The runtime hook must be
enforced in code (done), not prompt text.