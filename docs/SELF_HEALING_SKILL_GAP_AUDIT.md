# STRATX QUANTITATIVE RESEARCH SKILL LAYER — GAP AUDIT
**Date**: 2026-08-16  
**Auditor**: OMP Runtime Engineer  
**Scope**: Codebases across `C:\Trading\DE40-Research`, `C:\Trading\StratX-Quant-Agent`, `C:\Trading\Knowledge-Graph`, `C:\Trading\Terminal-X-V2-Recovered`.

---

## 1. EXECUTIVE SUMMARY

The physical agent runtime (DeepSeek V4 Pro on Ollama/Alibaba, DeepSeek V4 Flash on Ollama, MT5 native Strategy Tester, event logs, persistent daemon, watchdog) is operational.
However, a major gap exists in the **executable quantitative scientific layer**: previous iterations relied too heavily on unstructured LLM prompting rather than deterministic, mathematical, and forensic tools.

This audit classifies the 15 required shared quantitative skills into 4 standard categories:
* `EXISTS_AND_GOOD`: Fully implemented, tested, and meeting requirements.
* `EXISTS_BUT_INCOMPLETE`: Partially implemented (e.g. ad-hoc script or basic helper) requiring standardization and hardening.
* `MISSING`: No executable deterministic implementation present in the active research tree.
* `BROKEN`: Present but defective, leaking future data, or failing accounting reconciliation.

---

## 2. DETAILED SKILL-BY-SKILL AUDIT MATRIX

| Skill ID | Skill Name | Primary Responsibility | Current Status | Audit Findings & Required Enhancements |
|---|---|---|---|---|
| **SKILL 1** | `trade_population_analyzer` | Logical strategy position aggregation, R0 risk normalization, partials/scale-outs handling, PF reconciliation check | `EXISTS_BUT_INCOMPLETE` | `DE40-Research/scripts/forensics.py` parses CSVs but lacks position-level aggregation for scale-outs/partials, R0 dollar risk normalization, and strict `ACCOUNTING_INCONSISTENCY` reconciliation (`PF == (WR/(1-WR))*Payoff`). |
| **SKILL 2** | `cluster_detector` | Loss & winner multi-dimensional clustering, run-length scan statistics, session/volatility concentration | `EXISTS_BUT_INCOMPLETE` | `forensics.py` has basic feature tercile slices (`families` command), but lacks run-length analysis, scan statistics, binomial permutation tests, and winner cluster comparisons. |
| **SKILL 3** | `regime_tagger` | Point-in-time market regime tagging without future leakage, versioned feature definitions | `MISSING` | Feature generation was embedded ad-hoc inside MQL5 EAs without a standalone, versioned, point-in-time regime calculation engine. |
| **SKILL 4** | `causal_decomposer` | Losers vs Matched Winners comparison, odds ratio, effect size, Fisher exact / chi-square tests, confounder detection | `MISSING` | Previous research relied on naive observational filtering (*"losers often have low displacement -> add displacement filter"*) without matched-winner controls or confounder elimination. |
| **SKILL 5** | `failure_mode_classifier` | Extensible 20-category failure taxonomy, intervention memory tracking | `MISSING` | No formalized failure mode classifier. Strategy failures were described in freeform text without structured taxonomy or intervention tracking. |
| **SKILL 6** | `hypothesis_evidence_engine` | First-class scientific beliefs & hypotheses with status lifecycle and revision tracking | `EXISTS_BUT_INCOMPLETE` | `StratX-Quant-Agent/research/hypothesis_generator.py` exists as a stub, but lacks first-class belief objects, evidence links, and belief revisions without history loss. |
| **SKILL 7** | `child_parent_delta` | Position-by-position matching (Same, Removed, New, Loser->Winner, Winner->Loser, MAE/MFE delta, Frequency delta) | `EXISTS_BUT_INCOMPLETE` | Basic trade diff in `forensics.py` checks line counts, but lacks granular trade-by-trade classification explaining *why* performance changed. |
| **SKILL 8** | `structural_mutation_engine` | Translates canonical `EXPERIMENT_SPEC` (L1-L5) into code & verifies `IMPLEMENTATION_RECEIPT` | `MISSING` | MQL5 mutations were applied manually or via unstructured prompts. No deterministic comparison between `EXPERIMENT_SPEC` and `IMPLEMENTATION_RECEIPT` existed. |
| **SKILL 9** | `parameter_landscape_explorer` | Parameter sensitivity, broad plateaus vs knife-edge overfit spikes, interaction surfaces | `MISSING` | Grid searches existed in MT5 XML/opt format, but no automated plateau-breadth vs fragile-spike classifier was integrated. |
| **SKILL 10** | `overfitting_guard` | DEV/VAL discipline, Monte Carlo trade permutation, trial-count tracking, Deflated Sharpe Ratio | `EXISTS_BUT_INCOMPLETE` | Python scripts in `Terminal-X-V2-Recovered/tests` had isolated Monte Carlo routines, but they were not connected to the active DE40/X1X research pipeline. |
| **SKILL 11** | `research_policy_learner` | Meta-Self-Healing: Stores research-method policies (`FILTER_ACCRETION -> EARLY_THESIS_REVIEW`) | `MISSING` | **Critical missing layer**: System learned strategy-level lessons (*"ATR filter worked"*), but never learned research-method policies to alter future investigation behaviour. |
| **SKILL 12** | `evidence_dependency_graph` | Lineage tracking from feature version to module freeze, automatic `INVALIDATED_<CAUSE>` quarantine | `MISSING` | When the telemetry indexing bug was discovered, dependent evidence had to be audited manually. An automated dependency graph with cascade invalidation is required. |
| **SKILL 13** | `research_map_eiv` | Multi-dimensional exploration coverage (UNEXPLORED..EXHAUSTED) & Expected Information Value (EIV) ranking | `EXISTS_BUT_INCOMPLETE` | Basic territory list existed in `research_map.py`, but lacked multi-dimensional exploration scoring and deterministic EIV ranking. |
| **SKILL 14** | `research_exhaustion_engine` | Software-governed proof of `FAMILY_EXHAUSTED` (without mission halt) | `MISSING` | Exhaustion was decided subjectively by LLMs rather than via deterministic evidence checks (all major hypotheses tested, plateaus surveyed, EIV below threshold). |
| **SKILL 15** | `portfolio_gap_analyzer` | Cross-module return correlation, same-day/session overlap, tail risk, and missing alpha classification | `MISSING` | No automated tool analyzed portfolio gaps across accumulated modules to direct subsequent module discovery. |

---

## 3. IMPLEMENTATION ROADMAP

The shared executable quantitative skill layer will be implemented in `C:\Trading\DE40-Research\skills\` as modular, pure-Python modules with zero heavy dependencies, accompanied by a unified CLI (`skills/unified_cli.py`) and a comprehensive deterministic test suite:

1. **Phase 1 — Empirical Truth & Forensics**: `trade_population_analyzer`, `regime_tagger`, `child_parent_delta`.
2. **Phase 2 — Causal Inference & Hypotheses**: `cluster_detector`, `causal_decomposer`, `failure_mode_classifier`, `hypothesis_evidence_engine`.
3. **Phase 3 — Structural Code & Verification**: `structural_mutation_engine` (Spec vs Receipt validator), `parameter_landscape_explorer`.
4. **Phase 4 — Anti-Overfit & Meta-Learning**: `overfitting_guard`, `research_policy_learner` (Meta-Self-Healing), `evidence_dependency_graph`.
5. **Phase 5 — Search & Portfolio Intelligence**: `research_map_eiv`, `research_exhaustion_engine`, `portfolio_gap_analyzer`.
6. **Phase 6 — Testing & Smoke Test**: Full regression test suite + end-to-end blind research pipeline smoke test.
