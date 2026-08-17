"""
StratX Quant Skill 6: Belief + Hypothesis Engine
Maintains first-class scientific beliefs (PROPOSED, SUPPORTED, WEAKENING, REFUTED, RETIRED)
and first-class hypotheses with non-destructive revision tracking and falsification conditions.
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid

class HypothesisEvidenceEngine:
    def __init__(self):
        self.beliefs: Dict[str, Dict[str, Any]] = {}
        self.hypotheses: Dict[str, Dict[str, Any]] = {}
        self.revisions: List[Dict[str, Any]] = []

    def create_belief(self, claim: str, scope: str, initial_confidence: float = 0.5, supporting_evidence: Optional[List[str]] = None) -> str:
        bid = f"BELIEF_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.beliefs[bid] = {
            "belief_id": bid,
            "claim": claim,
            "scope": scope,
            "confidence": initial_confidence,
            "status": "PROPOSED",
            "supporting_evidence_ids": supporting_evidence or [],
            "contradicting_evidence_ids": [],
            "created_at": now,
            "updated_at": now,
            "revision_history": []
        }
        return bid

    def revise_belief(self, belief_id: str, new_status: str, new_confidence: float, reason: str, evidence_id: Optional[str] = None):
        """
        Revises a belief without destroying historical record.
        """
        if belief_id not in self.beliefs:
            raise KeyError(f"Belief {belief_id} not found.")

        b = self.beliefs[belief_id]
        prev_snapshot = {
            "status": b["status"],
            "confidence": b["confidence"],
            "timestamp": b["updated_at"],
            "reason": reason
        }
        b["revision_history"].append(prev_snapshot)
        b["status"] = new_status
        b["confidence"] = new_confidence
        b["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if evidence_id:
            if new_status in ["WEAKENING", "REFUTED", "RETIRED"]:
                b["contradicting_evidence_ids"].append(evidence_id)
            elif new_status == "SUPPORTED":
                b["supporting_evidence_ids"].append(evidence_id)

        self.revisions.append({
            "belief_id": belief_id,
            "previous": prev_snapshot,
            "current": {"status": new_status, "confidence": new_confidence},
            "reason": reason
        })

    def create_hypothesis(self, observation_ids: List[str], causal_theory: str, predicted_effect: str, falsification_condition: str, distinguishing_experiment: str) -> str:
        hid = f"HYP_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.hypotheses[hid] = {
            "hypothesis_id": hid,
            "observation_ids": observation_ids,
            "causal_theory": causal_theory,
            "predicted_effect": predicted_effect,
            "predicted_damage": "Potential trade frequency reduction",
            "falsification_condition": falsification_condition,
            "distinguishing_experiment": distinguishing_experiment,
            "confidence": 0.5,
            "status": "PROPOSED",
            "created_at": now
        }
        return hid

    def get_active_beliefs(self) -> List[Dict[str, Any]]:
        return [b for b in self.beliefs.values() if b["status"] not in ["REFUTED", "RETIRED"]]

    def get_hypotheses(self) -> List[Dict[str, Any]]:
        return list(self.hypotheses.values())
