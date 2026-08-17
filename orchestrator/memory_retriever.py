"""
StratX Context Budget & Top-K Memory Retriever (memory_retriever.py)
Prevents context window blowout and memory decay:
1. Scores tripartite memories by semantic tag similarity and failure signature relevance.
2. Selects top-K (default 3-5) most informative Strategy/Belief/Policy records.
3. Enforces strict token budget capping (< 4,000 tokens) to preserve context for the 219+ trade ledger.
"""

from typing import Dict, Any, List, Optional
import json

class MemoryRetriever:
    MAX_MEMORY_CHARS = 14000 # ~3,500 tokens

    def score_memory_relevance(self, memory: Dict[str, Any], query_tags: List[str]) -> float:
        """Computes relevance score between query tags and memory signature."""
        score = 0.0
        query_set = set(t.lower() for t in query_tags)

        # 1. Failure signature matching
        fs = memory.get("failure_signature", {})
        fam = fs.get("family", "").lower()
        if fam in query_set:
            score += 3.0
        for s in fs.get("symptoms", []):
            if any(q in s.lower() for q in query_set):
                score += 1.5

        # 2. Trigger pattern matching
        trig = memory.get("future_trigger", "").lower()
        if any(q in trig for q in query_set):
            score += 2.5

        # 3. Strategy family matching
        strat_fam = fs.get("strategy_family", "").lower()
        if strat_fam in query_set:
            score += 2.0

        # 4. Confidence weighting
        conf = float(memory.get("confidence", 0.8))
        score *= conf

        return score

    def retrieve_top_k(
        self,
        memories: List[Dict[str, Any]],
        query_tags: List[str],
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-K most relevant memories within strict token budget.
        """
        if not memories:
            return []

        scored = []
        for m in memories:
            sc = self.score_memory_relevance(m, query_tags)
            scored.append((sc, m))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = []
        total_chars = 0

        for sc, m in scored[:top_k * 2]: # inspect candidates
            # Serialize candidate
            summary = {
                "memory_id": m.get("memory_id"),
                "failure_signature": m.get("failure_signature"),
                "hypothesis_tested": m.get("hypothesis_id"),
                "experiment_verdict": m.get("experiment_verdict"),
                "strategy_lesson": m.get("strategy_lesson"),
                "research_method_lesson": m.get("research_method_lesson"),
                "future_trigger": m.get("future_trigger"),
                "future_behavior": m.get("future_behavior")
            }
            dump = json.dumps(summary)
            if total_chars + len(dump) > self.MAX_MEMORY_CHARS and selected:
                break
            
            selected.append(summary)
            total_chars += len(dump)
            if len(selected) >= top_k:
                break

        return selected
