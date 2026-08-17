# 🏛️ StratX Quants: Autonomous Quantitative Strategy Creation & Deep Self-Healing Engine

StratX Quants is an autonomous quantitative research and algorithmic trading platform designed to systematically reverse-engineer, hypothesize, build, test, diagnose, debate, repair, stress-test, and deploy institutional-grade trading strategies on MetaTrader 5 (MT5).

---

## 🎯 Core Operating Doctrine

> *"Never tell an agent: 'Keep trying until you reach 70% win rate.'  
> Tell it: 'Identify the largest evidence-backed failure mode, determine why it occurs, obtain independent council review, design the smallest experiment capable of proving or disproving the hypothesis, change only the necessary component, and measure every direct and secondary consequence.'  
> The purpose of QUANTS is not to brute-force profitable backtests. Its purpose is to:  
> **Discover → Hypothesise → Build → Test → Diagnose → Debate → Repair → Validate → Stress → Release → Learn**  
> Every mission must leave StratX smarter than before, whether the strategy passes or fails."*

---

## 🏛️ Multi-Model LLM Council Architecture

The deliberation pipeline decomposes strategy research into 7 specialized quantitative roles:

| Council Role | Model Engine | Specialization |
| :--- | :--- | :--- |
| **`STATISTICIAN`** | `zai-org/glm-5.2:thinking` (NanoGPT) | Deflated Sharpe Ratio (DSR), multiple testing bias & degrees of freedom audit |
| **`RED TEAM SKEPTIC`** | `zai-org/glm-5.2:thinking` (NanoGPT) | Adversarial edge refutation & over-filtering vulnerability probe |
| **`MARKET STRUCTURE SPECIALIST`** | `deepseek-v4-pro-0813` (Alibaba Cloud) | Order-flow analysis, session liquidity sweeps & microstructure |
| **`COUNCIL JUDGE`** | `deepseek-v4-pro-0813` (Alibaba Cloud) | Consensus synthesis, confidence scoring & research question formulation |
| **`MQL5 ARCHITECT`** | `deepseek-v4-pro-0813` (Alibaba Cloud) | 6-Block C++/MQL5 code synthesis with zero compiler errors |
| **`QUANT RESEARCHER`** | `deepseek-v4-pro:0813-cloud` (Ollama Pro) | Economic rationale & anomaly validation |
| **`EXECUTION SPECIALIST`** | `deepseek-v4-pro:0813-cloud` (Ollama Pro) | Spread sensitivity, tick points, slippage & broker execution |
| **`STRATX HISTORIAN`** | `deepseek-v4-pro:0813-cloud` (Ollama Pro) | Memory query of past lessons & failed setups |

---

## 🛡️ Persistent `SELF_REVIEW_GOAL` State Machine

StratX Quants operates under persistent Goal IDs (e.g. `SR_M1_001` for Module 1 `X1X_M1_FBO`):

1. **Evidence Provenance & Sample-Size Discipline**:
   - $N < 5$ trades is flagged as `FREQUENCY_COLLAPSE` / `SAMPLE_INSUFFICIENT`.
   - Loss clustering is blocked on single surviving trades.
2. **Child-Parent Delta Analysis (`compute_child_parent_delta`)**:
   - Measures exact trade population changes and over-filtering gate restrictions.
3. **Compounding TommyLoop Champion Carry-Forward**:
   - Compiles code physically via MetaEditor and executes against 28,213 real broker bars on Vantage MT5.
   - Promotes champions on verified fitness and rolls back on performance regressions.

---

## 🚀 Quickstart

```powershell
# Clone repository
git clone https://github.com/TommyAEM/stratx-quants.git
cd stratx-quants

# Launch the interactive Quantitative Research Desk
.\Start-StratX-QuantDesk.ps1
```
