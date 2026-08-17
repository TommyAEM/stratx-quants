# STRATX QUANTITATIVE RESEARCH ENGINE
## Master Multi-Role Agent Workflow, Persistent Goal Loop & Architecture Specification
**Document Version:** 3.0.0 (Production Architecture)  
**Classification:** Institutional Algorithmic Research Architecture  
**Author:** StratX Quantitative Engineering & Google DeepMind Antigravity  

---

## 1. CORE ARCHITECTURAL DOCTRINE

> **"The Python/Node orchestrator owns the loop. DeepSeek owns the intelligence inside the loop."**
> 
> *The central research loop is not: `while PASS_GATE_MET == False: mutate again`.*  
> *The central research loop is: `while SELF_REVIEW_GOAL unresolved: diagnose → learn → experiment → validate → reflect → escalate if necessary → loop again`.*

### Invariants of the System:
1. **Subtask Complete $\neq$ Mission Complete**: An individual role or tool finishing its work does not return control to the user. It emits evidence and triggers an automatic software-level role handoff.
2. **Todo List Complete $\neq$ Self-Review Complete**: Self-Review is **goal-based**, not checklist-based. It owns an immutable goal and loops recursively until the goal passes or formal escalation occurs.
3. **Safety Threshold Escalation $\neq$ Mission Stop**: Reaching an iteration threshold (e.g. 15 iterations) does not terminate research. It triggers escalation up the repair ladder ($L1 \to L2 \to L3 \to L4 \to L5$) while the mission remains `ACTIVE`.
4. **Mandatory Tripartite Memory Commitment on Every Iteration**: Every cycle commits **Strategy Memory**, **Belief Memory**, and **Research Policy Memory**. An iteration cannot close without all three.
5. **Pre-Compute Proposal Gate**: No code is generated and no MT5 tester is run until the proposal passes validation against prior memories and policy rules (preventing costly duplicate tests).

---

## 2. THE MASTER CLOSED-LOOP RESEARCH STATE MACHINE

```text
                             MISSION ACTIVE
                                   ↓
                   LOAD CURRENT SELF-REVIEW GOAL
                   (e.g. M1 Payoff Repair: WR>=70%, PF>=2.0, RR>=1.0)
                                   ↓
                   QUERY TRIPARTITE POLICY MEMORY
                   (Retrieve relevant strategy/belief/policy lessons)
                                   ↓
               FORENSIC ANALYST (DeepSeek Flash)
               - Ingest real MT5 trade ledger (219+ trades)
               - Point-in-time regime tagging (Zero-Lookahead)
               - Statistically rigorous cluster detector (BH-FDR q<=0.05)
               - Matched-winner causal decomposition (Fisher's exact)
                                   ↓
               HEAD QUANT / SELF-HEALER (DeepSeek Pro)
               - Structured Reflection (Predicted vs Actual vs Broken)
               - Update Causal Belief Network (Confidence deltas)
               - Formulate Competing Hypotheses (H1, H2, H3...)
               - Document evidence FOR and evidence AGAINST each
                                   ↓
               EXPERIMENT PLANNER (DeepSeek Pro)
               - Select Highest-EIV Distinguishing Experiment
               - Formulate Experiment Spec (L1-L5 Repair Level)
               - Declare Falsification Condition & Predicted Damage
                                   ↓
               PRE-COMPUTE PROPOSAL GATE (Python)
               - Check against FAILED_IN_CONTEXT prior tests
               - Check for multi-filter accretion policy violations
               - Verify explicit MEMORY_USED citation & reasoning
                 ├── REJECTED ──→ Loop back to Planner/Hypotheses
                 └── APPROVED ↓
               MQL5 ARCHITECT / CODER (DeepSeek Flash)
               - Implement MQL5 source mutation & .SET parameters
               - Generate Implementation Receipt (Hash verification)
               - Compile check (0 errors, 0 warnings)
                                   ↓
               MT5 RUNNER (Native Terminal Sandbox)
               - Execute physical backtest with 100% real broker ticks
               - Generate canonical Child Trade Population
                                   ↓
               REPORT ANALYST (DeepSeek Flash)
               - Calculate Child vs Parent Delta
               - Isolate Same, Removed (Losers vs Winners), New trades
                                   ↓
               MANDATORY CHILD RE-FORENSICS (DeepSeek Flash)
               - Re-run cluster detector & regime tagger on Child
               - Construct UPDATED failure map (preventing stale repairs)
                                   ↓
               ┌─────────────────────────────────────────────────────────────┐
               │                 MANDATORY SELF-REVIEW LOOP                  │
               │                                                             │
               │  1. What did we predict?                                    │
               │  2. What actually happened?                                 │
               │  3. Did child change trade population as expected?          │
               │  4. Did it fix the targeted failure family?                 │
               │  5. Did it introduce a new dominant failure?                │
               │  6. What improved?                                          │
               │  7. What was damaged?                                       │
               │  8. Was causal hypothesis supported, weakened or refuted?   │
               │  9. Was experiment capable of testing hypothesis?           │
               │ 10. Did MQL5 implementation faithfully match spec?          │
               │ 11. Did we learn something unexpected?                      │
               │ 12. What did we learn about the strategy?                   │
               │ 13. What did we learn about our research method?            │
               │ 14. Should our next research behavior change?               │
               └──────────────────────────────┬──────────────────────────────┘
                                              ↓
               MANDATORY TRIPARTITE MEMORY COMMITMENT
               - Commit Strategy Memory (Market symptoms & trade delta)
               - Commit Belief Memory (Causal belief status update)
               - Commit Research Policy Memory (Future trigger & behavior)
                                              ↓
                        DETERMINISTIC GOAL EVALUATOR (Python)
                                 Is Goal Passed?
                        ┌─────────────────────┴─────────────────────┐
                        NO                                          YES
                        ↓                                            ↓
               Advance Iteration                         INDEPENDENT REVIEWER
               Check Repair Ladder                       (DeepSeek Pro - Adversarial)
               (L1->L2->L3->L4->L5)                      - Plateau breadth audit
               Auto-Loop Back to                         - Overfitting/VAL check
               SAME Self-Review Goal                     - Monte Carlo permutations
                                                                     │
                                                 ┌───────────────────┴───────────────────┐
                                                 REJECT (Objections)                     PASS
                                                 ↓                                       ↓
                                         Reopen SELF-REVIEW                      RESEARCH GOVERNOR
                                         with reviewer objections                (DeepSeek Pro)
                                                                                 - Strategic Portfolio Fit
                                                                                 - Multi-Module Diversification
                                                                                 - Final Module Admission
                                                                                         │
                                                                         ┌───────────────┴───────────────┐
                                                                         REOPEN                          CLOSE GOAL
                                                                         Reopen with new                 Mark Goal PASSED
                                                                         constraints                     Admit Module
```

---

## 3. MODEL ROUTING & DIVISION OF LABOR

| Role Name | Assigned Model | Provider / Execution Mode | Responsibilities |
| :--- | :--- | :--- | :--- |
| **SUPERVISOR / GOVERNOR** | `alibaba/deepseek-v4-pro-0813` | Alibaba Cloud (Max Thinking) | Mission lifecycle, escalation gates, strategic portfolio admission |
| **HEAD QUANT / SELF-HEALER** | `alibaba/deepseek-v4-pro-0813` | Alibaba Cloud (Max Thinking) | Causal inference, belief revision, competing hypotheses ($H_1 \dots H_n$) |
| **EXPERIMENT PLANNER** | `alibaba/deepseek-v4-pro-0813` | Alibaba Cloud (Max Thinking) | EIV ranking, parameter landscape exploration, distinguishing experiment specs |
| **INDEPENDENT REVIEWER** | `alibaba/deepseek-v4-pro-0813` | Alibaba Cloud (Max Thinking) | Adversarial review, plateau stability audit, overfitting/VAL partition check |
| **FORENSIC ANALYST** | `ollama/deepseek-v4-flash:0731` | Local Ollama (Fast Execution) | Canonical trade parsing, cluster detection, regime tagging, matched winners |
| **MQL5 ARCHITECT / CODER** | `ollama/deepseek-v4-flash:0731` | Local Ollama (Fast Execution) | MQL5 code mutation, .SET file generation, syntax compilation verification |
| **REPORT ANALYST** | `ollama/deepseek-v4-flash:0731` | Local Ollama (Fast Execution) | Child vs Parent delta, trade-by-trade accounting reconciliation |

*Invariant: DeepSeek Pro is strictly forbidden from executing raw terminal tools in the main thread; all execution is delegated to DeepSeek Flash subagents or the Python orchestrator.*

---

## 4. THE 17 DETERMINISTIC QUANTITATIVE SKILLS

All quantitative logic is implemented in deterministic Python modules (`C:\Trading\DE40-Research\skills\`):

| # | Skill Name | Module File | CLI Subcommand | Function / Scientific Rigor |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `TradePopulationAnalyzer` | `trade_population_analyzer.py` | `trade_population` | Canonical trade parsing, MT5 alias mapping, zero-lookahead accounting |
| **2** | `ClusterDetector` | `cluster_detector.py` | `detect_clusters` | Pooled two-proportion $z$-test ($p = \text{erfc}(\|z\|/\sqrt{2})$), Benjamini-Hochberg FDR ($q \le 0.05$), Fisher's exact fallback |
| **3** | `RegimeTagger` | `regime_tagger.py` | `tag_regimes` | Point-in-time volatility terciles, session buckets, trend regimes |
| **4** | `CausalDecomposer` | `causal_decomposer.py` | `causal_decompose` | Matched-winner controls, Haldane-Anscombe Odds Ratio, Cohen's $d$ |
| **5** | `FailureModeClassifier` | `failure_mode_classifier.py` | `classify_failure` | Formal taxonomy (Validation Collapse, Filter Accretion, Slippage Fragility) |
| **6** | `HypothesisEvidenceEngine` | `hypothesis_evidence_engine.py` | `hypothesis_evidence` | First-class belief network with non-destructive versioned updates |
| **7** | `ChildParentDelta` | `child_parent_delta.py` | `child_parent_delta` | Position matching, Same/Removed/New trade decomposition, net $R$ delta |
| **8** | `StructuralMutationEngine` | `structural_mutation_engine.py` | `validate_experiment` | L1–L5 Experiment Spec vs Implementation Receipt cryptographic hash match |
| **9** | `ParameterLandscapeExplorer`| `parameter_landscape_explorer.py` | `explore_landscape` | Surface classification: Broad Stable Plateau vs Overfit Spike |
| **10**| `OverfittingGuard` | `overfitting_guard.py` | `audit_overfit` | DEV vs VAL performance retention, Monte Carlo permutations |
| **11**| `ResearchPolicyLearner` | `research_policy_learner.py` | `evaluate_action` | Trigger-action pattern matching, research method meta-learning |
| **12**| `EvidenceDependencyGraph` | `evidence_dependency_graph.py` | `dependency_graph` | DAG of beliefs/artifacts with automated cascade invalidation on defect |
| **13**| `ResearchMapEIVEngine` | `research_map_eiv.py` | `rank_eiv` | Expected Information Value ranking across strategy families |
| **14**| `ResearchExhaustionEngine` | `research_exhaustion_engine.py`| `evaluate_exhaustion`| Empirical exhaustion certification (prevents premature abandonment) |
| **15**| `PortfolioGapAnalyzer` | `portfolio_gap_analyzer.py` | `portfolio_gap` | Multi-strategy portfolio orthogonality & regime gap analysis |
| **16**| `SelfReviewEngine` | `self_review_engine.py` | `self_review` | Persistent Goal-Based Self-Review Engine & 14-point review recorder |
| **17**| `TripartiteMemoryEngine` | `tripartite_memory_engine.py` | `tripartite_memory` | Strategy + Belief + Policy memory model & Pre-Compute Proposal Gate |

---

## 5. PERSISTENT GOAL STATE MODEL & ESCALATION LADDER

### Goal Session Structure:
```json
{
  "self_review_id": "SREV_BEBC4400",
  "mission_id": "de40-x1x",
  "module_id": "M1_VPPOC",
  "parent_id": "CANDIDATE_PARENT",
  "current_candidate_id": "CANDIDATE_IT3",
  "goal_id": "GOAL_M1_PAYOFF_REPAIR",
  "goal_definition": "Repair M1 payoff architecture while preserving validated entry edge",
  "goal_metrics": {
    "win_rate": 0.70,
    "profit_factor": 2.0,
    "risk_reward": 1.0,
    "min_trades_per_year": 20.0
  },
  "goal_constraints": {
    "max_drawdown": 1000.0,
    "require_val_retention": true
  },
  "goal_status": "ACTIVE | TESTING | REASSESSING | PASSED | ESCALATE | BLOCKED",
  "iteration": 3,
  "history": [ "Records of iterations 1..N" ]
}
```

### The 5-Level Repair Ladder:
When consecutive iterations fail at the current level, the orchestrator automatically steps up the repair ladder:
```text
L1: PARAMETER TUNING
    └─ Adjust existing input thresholds within verified plateaus.
    └─ If 3 consecutive attempts fail ↓
L2: RULE / FILTER GATING
    └─ Introduce a single targeted mechanical regime gate (BH-FDR verified).
    └─ If 3 consecutive attempts fail ↓
L3: COMPONENT REFACTOR
    └─ Replace stop architecture, split runners, or refactor execution model.
    └─ If 3 consecutive attempts fail ↓
L4: ARCHITECTURE OVERHAUL
    └─ Redesign indicator pipeline, profile calculation, or state machine.
    └─ If 3 consecutive attempts fail ↓
L5: THESIS / FAMILY PIVOT
    └─ Escalate to Head Quant / Research Map to explore new alpha family.
```

---

## 6. TRIPARTITE MEMORY & EVOLUTIONARY LEARNING

Every single iteration commits three layers of persistent memory:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TRIPARTITE MEMORY RECORD                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. STRATEGY MEMORY                                                          │
│    - Failure signature & symptoms (PF up, trade frequency down, WR stable) │
│    - Child-parent delta (11 losers removed, 9 winners removed)              │
│    - Market behavior lesson: "Gate mostly suppresses trades"                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. BELIEF MEMORY                                                            │
│    - Prior belief: "High displacement identifies higher-quality VWAP fades" │
│    - Updated status: WEAKENED (Confidence delta: -0.31)                     │
│    - Verdict: HYPOTHESIS_NOT_SUPPORTED                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. RESEARCH POLICY MEMORY                                                   │
│    - Future Trigger: "PF_UP + FREQUENCY_DOWN + BASE_WR_STABLE"              │
│    - Future Behavior: "Trigger early thesis review instead of adding gate"  │
│    - Policy Rule: PREFER_SINGLE_CAUSAL_GATES                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pre-Compute Proposal Gate Enforcement:
Before dispatching MQL5 compilation or MT5 backtests, the proposed experiment must pass:
1. **Duplicate Rejection (`FAILED_IN_CONTEXT`)**: If an experiment resembles a prior failed test, it is rejected unless DeepSeek provides `repeat_justification` and `material_context_difference` (e.g. *"Re-evaluating after fixing telemetry bug"*).
2. **Policy Compliance**: Proposing a 3-gate filter stack is rejected if active policy mandates `PREFER_SINGLE_CAUSAL_GATES`.
3. **Auditable Provenance Citation**: DeepSeek must state `MEMORY_USED` and `HOW_THEY_CHANGED_THIS_DECISION`.

---

## 7. FULL REPOSITORY TEST SUITE VERIFICATION

The entire quantitative infrastructure has been validated with 100% test pass rates across 26 automated suites:

* **Unit Test Suite**: [`tests/test_quant_skills_suite.py`](file:///C:/Trading/DE40-Research/tests/test_quant_skills_suite.py) (16/16 skills verified)
* **Goal Loop Acceptance Suite**: [`tests/test_self_review_and_loopback.py`](file:///C:/Trading/DE40-Research/tests/test_self_review_and_loopback.py) (5/5 tests verified)
* **Evolutionary Memory Suite**: [`tests/test_evolutionary_memory_loop.py`](file:///C:/Trading/DE40-Research/tests/test_evolutionary_memory_loop.py) (3/3 tests verified)
* **Master Orchestrator Suite**: [`tests/test_stratx_orchestrator_loop.py`](file:///C:/Trading/DE40-Research/tests/test_stratx_orchestrator_loop.py) (2/2 tests verified)

```text
Ran 26 tests in 0.010s -> 26/26 PASSED (100% OK)
```
