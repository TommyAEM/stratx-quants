"""
StratX Persistent Vector Database Brain & Confidence Scoring Engine (brain_vectordb.py)
Stores institutional quantitative memories, repair hypotheses, and MQL5 fix effectiveness with:
1. Instant Vector Embedding & Persistent Storage in ./stratx_brain (Zero-lag).
2. Dynamic Confidence Scoring Delta (+0.10 on pass, -0.15 on fail, clamped [0.0, 1.0]).
3. Cold-Start Boot Injection: Loads Top-5 VALIDATED fixes and Top-5 DEBUNKED failures into Head Quant.
"""

import os
import re
import json
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Optional

BRAIN_DIR = Path("C:/Trading/DE40-Research/stratx_brain")
BRAIN_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_FILE = BRAIN_DIR / "vector_memory_collection.json"

class FastVectorEmbedder:
    """Lightweight deterministic vectorizer for instant local semantic indexing without network downloads."""
    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        import hashlib
        vec = [0.0] * self.dim
        tokens = re.findall(r'\w+', text.lower())
        if not tokens:
            return vec
        for tok in tokens:
            # NOTE: Python's built-in hash() is salted per process (PYTHONHASHSEED), so
            # hash(tok) % dim differs between runs and makes stored vectors incomparable
            # across sessions. md5 is stable across processes.
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0
        # Normalize L2
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

embedder = FastVectorEmbedder(dim=64)

# ChromaDB Initialization with custom embedding fallback
CHROMADB_AVAILABLE = False
try:
    import chromadb
    brain_client = chromadb.PersistentClient(path=str(BRAIN_DIR))
    # Use get_or_create without default downloading embedding
    memory_collection = brain_client.get_or_create_collection(
        name="tripartite_memory",
        metadata={"hnsw:space": "cosine"}
    )
    CHROMADB_AVAILABLE = True
except Exception:
    CHROMADB_AVAILABLE = False

def _load_persistent_store() -> List[Dict[str, Any]]:
    if VECTOR_STORE_FILE.exists():
        try:
            return json.loads(VECTOR_STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_persistent_store(memories: List[Dict[str, Any]]):
    VECTOR_STORE_FILE.write_text(json.dumps(memories, indent=2), encoding="utf-8")

def commit_tripartite_memory(head_quant_result: Dict[str, Any], child_metrics: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Commits an experiment outcome to the Vector DB and updates confidence scores.
    Belief movement is evidence-quality weighted (sample size, validation stability,
    prediction match, implementation fidelity) and outcomes are contextual
    (SUPPORTED_IN_CONTEXT / REFUTED / INCONCLUSIVE...), not binary SUCCESS/FAILED."""
    tags = head_quant_result.get("memory_tags", ["GENERAL_REPAIR"])
    fix_description = head_quant_result.get("reasoning", "") or head_quant_result.get("recommended_fix", "MQL5 Strategy Mutation")
    passed = (child_metrics.get("win_rate", 0) >= 0.70 and 
              child_metrics.get("profit_factor", 0) >= 2.00 and 
              child_metrics.get("max_drawdown", 1.0) <= 0.06 and
              child_metrics.get("max_consecutive_losses", 99) <= 4)

    # --- Evidence-quality weight (Tier-2 §4) ---
    eq = state.get("last_evidence_quality") or {}
    weight = 1.0
    n = int(eq.get("n_trades", child_metrics.get("total_trades", 0)) or 0)
    if n < 5:
        weight *= 0.25
    elif n < 15:
        weight *= 0.60
    if eq and not eq.get("wf_evidence_available", True):
        weight *= 0.50
    elif eq and not eq.get("wf_passed", True):
        weight *= 0.60
    if eq.get("implementation_fidelity") == "MISMATCH":
        weight *= 0.30
    weight = max(0.10, min(1.50, weight))

    # --- Contextual outcome (Mission §12) ---
    belief = (state.get("last_self_review") or {}).get("causal_belief_update")
    if passed and belief == "SUPPORTED":
        outcome_context = "SUPPORTED_IN_CONTEXT"
    elif passed:
        outcome_context = "CONTEXT_DEPENDENT"
    elif belief == "REFUTED":
        outcome_context = "REFUTED"
    elif belief == "WEAKENED":
        outcome_context = "FAILED_IN_CONTEXT"
    else:
        outcome_context = "INCONCLUSIVE"
    
    it = state.get("iteration", 0)
    mission_id = state.get("mission_id", "de40-x1x")
    mem_id = f"MEM_{it:04d}_{mission_id}"
    
    memories = _load_persistent_store()
    old_confidence = 0.50
    for m in memories:
        if set(m.get("tags", [])) == set(tags):
            old_confidence = m.get("confidence", 0.50)
            break

    # Confidence delta scaled by evidence weight (+0.10 on pass, -0.15 on fail)
    if passed:
        new_confidence = min(1.0, old_confidence + 0.10 * weight)
    else:
        new_confidence = max(0.0, old_confidence - 0.15 * weight)
        
    if new_confidence >= 0.70:
        status = "VALIDATED"
    elif new_confidence <= 0.20:
        status = "DEBUNKED"
    else:
        status = "TESTING"

    doc_text = f"{' '.join(tags)}: {fix_description[:500]}"
    vector = embedder.embed(doc_text)

    # --- MemSkill-style evidence lineage: the fields that repeatedly prove ---
    # --- necessary to identify filter accretion are preserved on every record ---
    delta = state.get("last_child_parent_delta") or {}
    lineage = {
        "parent_trades": delta.get("parent_trades"),
        "child_trades": delta.get("child_trades"),
        "frequency_delta_pct": delta.get("pct_trade_change"),
        "frequency_retention_pct": delta.get("frequency_retention_pct"),
        "losers_removed": delta.get("losers_removed_count"),
        "winners_removed": delta.get("winners_removed_count"),
        "loser_to_winner": delta.get("loser_to_winner"),
        "winner_to_loser": delta.get("winner_to_loser"),
        "is_freq_collapse": delta.get("is_freq_collapse"),
        "is_sample_insufficient": delta.get("is_sample_insufficient"),
        "causal_hypothesis": (state.get("last_self_review") or {}).get("unmet_dimensions"),
        "validation_outcome": "PASS" if eq.get("wf_passed") else ("UNAVAILABLE" if not eq.get("wf_evidence_available", True) else "FAIL"),
        "matched_winner_comparison": eq.get("matched_winner_comparison"),
    }

    entry = {
        "id": mem_id,
        "document": doc_text,
        "tags": tags,
        "confidence": round(new_confidence, 2),
        "status": status,
        "passed": passed,
        "outcome_context": outcome_context,
        "evidence_weight": round(weight, 3),
        "evidence_lineage": lineage,
        "win_rate": round(child_metrics.get("win_rate", 0.0), 2),
        "profit_factor": round(child_metrics.get("profit_factor", 0.0), 2),
        "max_drawdown": round(child_metrics.get("max_drawdown", 0.0), 3),
        "max_consec_losses": child_metrics.get("max_consecutive_losses", 0),
        "total_trades": child_metrics.get("total_trades", 0),
        "vector": vector,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    memories.append(entry)
    _save_persistent_store(memories)

    if CHROMADB_AVAILABLE:
        try:
            memory_collection.add(
                embeddings=[vector],
                documents=[doc_text],
                metadatas=[{
                    "tags": ", ".join(tags),
                    "confidence": round(new_confidence, 2),
                    "status": status,
                    "mission_id": mission_id
                }],
                ids=[mem_id]
            )
        except Exception:
            pass

    return {
        "id": mem_id,
        "tags": tags,
        "confidence": round(new_confidence, 2),
        "status": status,
        "passed": passed,
        "outcome_context": outcome_context,
        "evidence_weight": round(weight, 3)
    }

def load_brain_context(query_tags: Optional[List[str]] = None) -> str:
    """Queries the Vector DB for the most successful past lessons & debunked failures to steer the agent."""
    memories = _load_persistent_store()
    
    validated = [m for m in memories if m.get("status") == "VALIDATED"]
    debunked = [m for m in memories if m.get("status") == "DEBUNKED"]
    
    # Sort by confidence
    validated.sort(key=lambda x: x.get("confidence", 0.8), reverse=True)
    debunked.sort(key=lambda x: x.get("confidence", 0.1))

    context = "=== INSTITUTIONAL BRAIN: ACCUMULATED VECTOR MEMORY & PLAYBOOK ===\n"
    if validated:
        context += "\n🏆 [HIGH-CONFIDENCE VALIDATED PLAYBOOK (PRIORITIZE THESE STRUCTURAL TOOLS)]:\n"
        for m in validated[:5]:
            context += f"• {m['document']} (Confidence: {m['confidence']:.2f} | WR: {m.get('win_rate',0)*100:.0f}% | PF: {m.get('profit_factor',0):.2f})\n"
    else:
        context += "\n🏆 [HIGH-CONFIDENCE VALIDATED PLAYBOOK]: Initializing benchmark alpha models.\n"
        
    if debunked:
        context += "\n🚫 [DEBUNKED STRUCTURAL FAILURES (FORBIDDEN TO REPEAT)]:\n"
        for m in debunked[:5]:
            context += f"• {m['document']} (Confidence: {m['confidence']:.2f} | Status: DEBUNKED)\n"
    else:
        context += "\n🚫 [DEBUNKED STRUCTURAL FAILURES]: None yet recorded.\n"
        
    return context
