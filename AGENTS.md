# StratX DE40 Research — Agent Master Index

**Read this first.** Autonomous quant research engine targeting a 5+ module uncorrelated DE40 (GER40) portfolio.
Institutional gates (corrected X1X multi-strategy spec): module = WR ≥ 70%, PF ≥ 2.00, Realised RR ≥ 1.00, ≥ 20 trades/yr, WF PASS, plateau/DSR robustness PASS, unique alpha PASS. Portfolio = 5–6 modules, combined ≥ 100 trades/yr, 1.00% risk/trade, ONE concurrent trade across ALL modules, combined MaxDD < 10%.

---

## 1. HARD RULES (verified ground truth — do not re-derive)

Full versions: `C:\Trading\Knowledge-Graph\graphify-nodes\learning_5..12.json` (+ obsidian mirrors in `obsidian-brain\learnings\2026-08-17_DE40_*`).

1. **UTF-16LE everywhere**: MetaEditor compile logs AND MT5 tester HTML reports. BOM/NUL-detect before decoding or every regex silently fails. (learning_5)
2. **MetaEditor CLI**: pass `/compile` `/log` UNQUOTED (quoted args silently dropped); single-instance → serialize; missing log = FAILURE; ground truth = `.ex5` exists. (learning_6)
3. **Test integrity**: metrics are only valid if the exact candidate EA ran: compile → physical tester → report → parse. Never accept harness-side simulations. (learning_7)
4. **MQL5 ≠ MQL4**: no `Hour()`/`High[]`/value-style `iMA/iATR/iADX`. Use `iTime/iHigh/iVolume`, `MqlDateTime`, handles + `CopyBuffer` + `ArraySetAsSeries`, `CTrade`, new-bar gate via `iTime`. (learning_8)
5. **No iCustom for VWAP/SuperTrend/CHOP/HMA/KAMA** — not installed on the terminal; compute natively. (learning_9)
6. **Prompts**: static-check f-string vars; repetition sever must raise `RepetitionLoopError` to the retry loop; NEVER fabricate "deterministic facts"; max 3 skills per phase. (learning_10)
7. **Tokens**: Pro (0813) = Head Quant + Reviewer + Pro-escalation only. Flash (0731, local) = Architect/syntax/forensic/planner. NanoGPT = 3rd Pro fallback. (learning_11)
8. **Environment**: symbol is `GER40` (not `GER40.s`); tester reports land in data-dir ROOT; headless tester is blocked while interactive MT5 runs (E07A data-dir lock) — close MT5 or use VantageResearch install. (learning_12)

## 2. ARCHITECTURE MAP (`orchestrator/`)

| File | Role | Status |
|---|---|---|
| `stratx_live_console.py` | Master loop: 9-role LLM pipeline, prompt architecture, `MODULE_THESES` (14 modules), gates | ✅ Audited & patched 2026-08-17 (champion carry-forward + 35-iter deep incubation + rollback + genetic sweep + simulated annealing) |
| `quant_skills.py` | Deterministic quant toolbelt; `route_quant_skills` = top-3 skills/phase via `PHASE_SKILL_MAP`; T-Quant significance test + complexity penalty gate champion promotion | ✅ Pruned & de-faked |
| `toolbox.py` | Indicator/SMC knowledge snippets (all MQL5-correct) | ✅ Fixed |
| `mt5_adapter.py` | MetaEditor compile bridge + headless tester runner + genetic optimization sweep (`Optimization=2`, `[TesterInputs]` ranges, winner-param scraper) + report/trades scrapers | ✅ UTF-16/CLI/report-path fixed |
| `real_quant_tester.py` | Physical backtest orchestration (compile → tester → parse) | ✅ Integrity rebuild |
| `optimizer_engine.py` | 5-stage optimization: Sobol QMC sampling → sequential physical MT5 batch → Pareto front → plateau/spike rejection → DSR multiple-testing gate | ✅ Added 2026-08-17 (stage tests green) |
| `brain_vectordb.py` | Vector memory + confidence scoring (md5-deterministic embeddings) | ✅ Fixed |
| `brain_memory.py` | Tag-based lesson store (`brain/stratx_brain.json`) | ⚠️ Dormant (not called by console) |
| `llm_client.py` | NanoGPT client + endpoint/key constants | ✅ Referenced by console gateways |
| `memory_retriever.py` | Top-K memory budget retriever | ⚠️ Dormant |
| `state_persistence.py` | Atomic checkpoint manager | ⚠️ Dormant (console has own `save_checkpoint`) |
| `chat_console.py` | Interactive steering pane (writes `directive.txt`) | OK |
| `stratx_goal_loop.py` | Legacy goal loop | ⚠️ Superseded by live console |

## 3. BRAIN / MEMORY STORES

| Store | Path | Written by | Authoritative? |
|---|---|---|---|
| Physical JSON brain | `stratx_brain.json` (root) | `write_to_brain` / `read_from_brain` | ✅ Yes — validated/debunked fixes |
| Vector memory | `stratx_brain/vector_memory_collection.json` (+ ChromaDB) | `commit_tripartite_memory` / `load_brain_context` | ✅ Yes — confidence-scored |
| Tagged lessons | `brain/stratx_brain.json` | `brain_memory.py` (dormant) | ⏸ Legacy |
| Checkpoint | `campaign_state.json` | `save_checkpoint` | ✅ Crash recovery |
| Knowledge-Graph | `C:\Trading\Knowledge-Graph\graphify-nodes\learning_*.json` | cross-project brain (`stratx_brain.py` CLI) | ✅ Shared institutional memory |

## 4. MODULE INVENTORY (14 compile-verified baselines in `MODULE_THESES`)

- M1 FVG Mitigation · M2 Asian Sweep · M3 Z-Score Chop Fade · M4 Opening Gap · M5 Donchian BOS (M15)
- M6 London Close Fade · M7 Asian Range Expansion · M8 DXY Inversion · M9 Opening FVG · M10 GMM-Proxy Momentum
- M11 Fib 0.618 + OLS Pullback (H1) · M12 Donchian Trend Ride (H1, ADX) · M13 OLS VWAP Pullback (H1) · M14 SuperTrend+MACD (H4)

Verified template sources: `ea/template_check/*.mq5` (all "0 errors" via production adapter). Mutate, never blank-canvas.

## 5. OPS RUNBOOK

- **Launch**: close interactive MT5 first (data-dir lock), then `python orchestrator/stratx_live_console.py` (or `start_stratx.bat`). Lock-free test instance: `C:\Users\Tommy\AppData\Roaming\VantageResearch\terminal64.exe` (same demo account).
- **Steer**: write `C:\Trading\DE40-Research\directive.txt` (consumed each iteration).
- **Keys**: Alibaba via `get_alibaba_key()` from `C:\Users\Tommy\AppData\Local\hermes\.env`; NanoGPT constants in `llm_client.py`; Ollama local `127.0.0.1:11434` (no key).
- **Verify a module**: `write_and_compile_mql5()` → log must say 0 errors AND `.ex5` must exist → `run_mt5_backtest` → `parse_mt5_report` / `parse_mt5_trades`.
- **Model routing**: `ROLE_MODEL_TIER` + `ROLE_MAX_TOKENS` in console; compile loop escalates Flash → Pro after 2 failures.

## 6. CURRENT STATE (2026-08-17)

Full pipeline verified end-to-end on physical ground truth (headless GER40 backtest on VantageResearch: 17 trades parsed, metrics+deals cross-checked). First live mission ran Forensic → Architect → `0 errors` compile, then halted at backtest due to the interactive-terminal lock. **Next action: close MT5, relaunch console, re-arm Sentinel watchdog.**
