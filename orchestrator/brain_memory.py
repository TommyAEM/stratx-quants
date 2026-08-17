"""
StratX Graphified Brain Memory Engine (brain_memory.py)
Structured persistent memory for quantitative learning:
- Commits tagged lessons learned from every iteration (e.g. [ATR, Volatility, FAILED]).
- Queries brain by intent/tags to prevent repetitive trial-and-error mistakes.
- Graph-indexed storage in JSON format.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

BRAIN_FILE = Path("C:/Trading/DE40-Research/brain/stratx_brain.json")
BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_brain() -> List[Dict[str, Any]]:
    """Loads all knowledge memories from disk."""
    if not BRAIN_FILE.exists():
        return []
    try:
        data = json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_brain(memories: List[Dict[str, Any]]):
    """Persists memories to disk in clean formatted JSON."""
    try:
        BRAIN_FILE.write_text(json.dumps(memories, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Brain Memory Save Error]: {e}")

def commit_memory(
    iteration: int,
    phase: str,
    repair_level: str,
    indicators_used: List[str],
    memory_tags: List[str],
    outcome: str,
    metrics: Dict[str, Any],
    lesson_learned: str
) -> Dict[str, Any]:
    """Records a structured tagged memory in the Quant Brain."""
    memories = load_brain()
    entry = {
        "id": f"MEM_{len(memories) + 1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "iteration": iteration,
        "phase": phase,
        "repair_level": repair_level,
        "indicators_used": indicators_used,
        "tags": [t.upper() for t in memory_tags],
        "outcome": outcome, # "PASSED" or "FAILED"
        "metrics": {
            "trades": metrics.get("total_trades", 0),
            "win_rate": round(metrics.get("win_rate", 0.0), 3),
            "profit_factor": round(metrics.get("profit_factor", 0.0), 2),
            "max_consec_losses": metrics.get("max_consecutive_losses", 0)
        },
        "lesson": lesson_learned
    }
    memories.append(entry)
    save_brain(memories)
    return entry

def query_brain_by_intent(forensic_summary: Dict[str, Any], top_k: int = 4) -> str:
    """
    Searches the Quant Brain for historical lessons matching recent failure modes or indicators.
    """
    memories = load_brain()
    if not memories:
        return "=== 🧠 GRAPHIFIED BRAIN MEMORY: [EMPTY - ITERATION 1 BASELINE] ==="

    # Extract search terms from forensic summary
    search_terms = []
    if isinstance(forensic_summary, dict):
        for val in forensic_summary.values():
            if isinstance(val, str):
                search_terms.extend(val.upper().replace(",", " ").split())
            elif isinstance(val, list):
                search_terms.extend([str(x).upper() for x in val])

    # Rank memories by tag/term overlap
    scored_memories = []
    for m in memories:
        score = 0
        m_tags = [t.upper() for t in m.get("tags", [])]
        m_inds = [i.upper() for i in m.get("indicators_used", [])]
        for term in search_terms:
            if any(term in tag for tag in m_tags):
                score += 2
            if any(term in ind for ind in m_inds):
                score += 1
        scored_memories.append((score, m))

    # Sort descending
    scored_memories.sort(key=lambda x: x[0], reverse=True)
    selected = [m for _, m in scored_memories[:top_k]] if scored_memories else memories[-top_k:]

    context = "=== 🧠 GRAPHIFIED QUANT BRAIN MEMORY (Relevant Lessons Learned) ===\n"
    for m in selected:
        status_sym = "✅" if m["outcome"] == "PASSED" else "❌"
        context += f"• [{m['id']}] {status_sym} Outcome: {m['outcome']} | Tags: {m['tags']} | Indicators: {m.get('indicators_used', [])}\n"
        context += f"  - Performance: Trades={m['metrics']['trades']}, WR={m['metrics']['win_rate']*100:.1f}%, PF={m['metrics']['profit_factor']}, MaxLossStreak={m['metrics']['max_consec_losses']}\n"
        context += f"  - Lesson: {m['lesson']}\n"
    
    return context
