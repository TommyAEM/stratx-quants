# 🏛️ StratX 3-Tier Self-Healing Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 1 — STRATEGY SELF-HEALING (The Quantitative Loop)                      │
│ "What is wrong with this EA and how do I repair it?"                        │
│                                                                             │
│ MT5 Backtest → Analyse Losers → Matched Winners → Find Clusters →           │
│ Child-Parent Delta → Single Causal Mutation → Test Child → Promote/Revert   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 2 — BRAIN / EXPERIENCE MEMORY (The Knowledge Graph)                     │
│ "What have we learned from previous experiments?"                           │
│                                                                             │
│ Experiment → Predicted Outcome → Actual Outcome → Belief Update (Delta) →   │
│ Strategy Lesson → Research Lesson → Persist Knowledge Graph → Retrieve      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 3 — META SELF-HEALING / SKILLOPT (The Recursive Evolutionary Layer)    │
│ "How should the researcher itself become better at researching?"             │
│                                                                             │
│ Harvest Many Missions → Identify Recurring Cognitive Failures →             │
│ Propose Bounded Skill Mutation → Replay Historical Benchmark Episodes →    │
│ Held-Out Validation Gate → Accept/Reject Skill Edit → Next Epoch            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Deep Breakdown of the 3 Tiers

### 🔵 Tier 1: Strategy Self-Healing (Live EA Adaptation)
- **Question Answered**: *"What is wrong with this EA and how do I repair it?"*
- **Operational Cycle**:
  1. **Physical MT5 Execution**: Backtest EA on 28,213 real broker bars with real spread and slippage modeling.
  2. **Loss & Matched-Winner Forensics**: Extract telemetry blotter, compute context (volatility, session, MAE/MFE).
  3. **Sample Provenance Guard**: If $N < 5$, flag `SAMPLE_INSUFFICIENT` and prioritize frequency restoration.
  4. **Child-Parent Delta Analysis**: Measure trade changes, gate restrictions, and isolate filter over-tightening.
  5. **Single Causal Mutation**: Modify exactly one structural block in the 6-Block MQL5 architecture.
  6. **Compounding TommyLoop**: Promote child if fitness improves and edge is statistically significant ($t \ge 2.5, p < 0.01$); otherwise rollback to champion.

---

### 🟢 Tier 2: Brain / Experience Memory (Institutional Knowledge Graph)
- **Question Answered**: *"What have we learned from previous experiments?"*
- **Operational Cycle**:
  1. **Tripartite Memory Record**:
     - **`Strategy Memory`**: Source code, parameters, trade count, WR, PF, DD.
     - **`Belief Memory`**: Prior belief vs posterior evidence with confidence delta ($\pm 0.15$ / $-0.20$).
     - **`Research Policy Memory`**: Methodological takeaways (e.g. *"Indices require asymmetrical short gating"*).
  2. **Evidence Dependency Lineage Graph**:
     - Tracks nodes: `FEATURE` $\to$ `OBSERVATION` $\to$ `HYPOTHESIS` $\to$ `EXPERIMENT` $\to$ `REPORT` $\to$ `FREEZE`.
     - Automatically cascades invalidation if an upstream foundation fails stress testing.
  3. **Pre-Compute Proposal Gate**:
     - Queries memory graph before compiling. Rejects duplicate or previously debunked experiments before burning compute.

---

### 🟣 Tier 3: Meta Self-Healing / SkillOpt (Evolutionary Cognitive Adaptation)
- **Question Answered**: *"How should the researcher itself become better at researching?"*
- **Operational Cycle**:
  1. **Session Harvesting (`SkillOpt-Sleep`)**: Collect research logs, LLM Council transcripts, and decision sequences across 50+ completed missions.
  2. **Cognitive Error Pattern Mining**: Identify recurring researcher mistakes (e.g., Filter Accretion, Confirmation Bias, Early Thesis Abandonment, Over-Optimizing R-Multiples).
  3. **Bounded Skill Mutation**: Propose minimal, high-impact edits to the agent's markdown skill instructions (`stratx-quant-self-heal.md`, `stratx-failure-autopsy.md`).
  4. **`STRATX_RESEARCH_BENCHMARK` Replay**: Run the mutated skill against a battery of historical training episodes.
  5. **Held-Out Validation Gate**: Evaluate the mutated skill against unseen research missions.
     - If the mutated skill produces higher research efficiency, fewer wasted runs, and better holdout retention $\to$ **PROMOTE TO PRODUCTION SKILL**.
     - If any regression occurs $\to$ **REJECT EDIT & RESTORE BASELINE SKILL**.

---

## 🛡️ Invariant Ground Rules Across All 3 Tiers

| Layer | Type | Mutability | Ownership |
| :--- | :--- | :--- | :--- |
| **System Invariants** | State Machine, 1% Risk, MT5 Exec, Pass Gates | **IMMUTABLE (Frozen)** | Deterministic Python & C++ Harness |
| **Tier 1 (Strategy)** | MQL5 Logic, Parameters, Rules, Indicators | **EVOLVABLE (Per Iteration)** | LLM Council & Physical MT5 Tester |
| **Tier 2 (Brain)** | Facts, Provenance, Historical Trials, Beliefs | **APPEND-ONLY (Per Experiment)** | Knowledge Graph (`stratx_brain.json`) |
| **Tier 3 (SkillOpt)** | Researcher Heuristics, Skill MDs, Prompt Guides | **EVOLVABLE (Per Epoch)** | Meta-Learner via Validation Gates |
