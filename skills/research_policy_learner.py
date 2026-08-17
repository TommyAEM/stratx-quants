"""
StratX Quant Skill 11: Research Policy Learner (Meta-Self-Healing)
Stores and retrieves research-method lessons so that past research mistakes
alter future investigation behaviour (e.g. recognizing filter accretion earlier).
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid

class ResearchPolicyLearner:
    def __init__(self):
        self.policies: Dict[str, Dict[str, Any]] = {}
        # Seed initial canonical StratX research policies
        self._seed_initial_policies()

    def _seed_initial_policies(self):
        self.record_policy(
            trigger_pattern="FILTER_ACCRETION_WITH_DROPPING_FREQUENCY",
            previous_behavior="Stacking 3+ consecutive filters to boost DEV PF while losing >40% of trades",
            outcome="Out-of-sample VAL collapse (severe overfit)",
            lesson="DEV forensic gates often overfit regime noise. Require VAL verification of single causal gate before stacking.",
            recommended_future_behavior="EARLY_THESIS_REVIEW (Ablate filters and review core entry architecture after 2 failed gate tests)"
        )
        self.record_policy(
            trigger_pattern="SHORT_DIRECTION_DRAG_ON_INDICES",
            previous_behavior="Attempting to force symmetrical short architectures across 2023-2025 index regimes",
            outcome="Persistent negative expectancy across all tested families",
            lesson="Index drift creates structural asymmetry. Separate long/short entry triggers or restrict shorts to high-volatility exhaustion.",
            recommended_future_behavior="ISOLATE_DIRECTION_ENGINES (Develop long-only baseline first before researching short regime filters)"
        )

    def record_policy(self, trigger_pattern: str, previous_behavior: str, outcome: str, lesson: str, recommended_future_behavior: str, confidence: float = 0.8) -> str:
        pid = f"POL_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.policies[pid] = {
            "policy_id": pid,
            "trigger_pattern": trigger_pattern,
            "previous_behavior": previous_behavior,
            "outcome": outcome,
            "lesson": lesson,
            "recommended_future_behavior": recommended_future_behavior,
            "confidence": confidence,
            "support_count": 1,
            "contradiction_count": 0,
            "created_at": now,
            "last_used": now,
            "status": "ACTIVE"
        }
        return pid

    def evaluate_research_action(self, current_action_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates a planned research action against stored policies to prevent repeat mistakes.
        """
        matches = []
        rules_count = current_action_context.get("rule_count", 0)
        freq_drop = current_action_context.get("freq_drop_pct", 0)
        direction = current_action_context.get("direction", "")

        for p in self.policies.values():
            if p["status"] != "ACTIVE":
                continue

            if p["trigger_pattern"] == "FILTER_ACCRETION_WITH_DROPPING_FREQUENCY":
                if rules_count >= 3 or freq_drop >= 40:
                    matches.append(p)
            elif p["trigger_pattern"] == "SHORT_DIRECTION_DRAG_ON_INDICES":
                if direction == "SHORT" and current_action_context.get("is_index", True):
                    matches.append(p)

        return matches

    def get_all_policies(self) -> List[Dict[str, Any]]:
        return list(self.policies.values())
