"""
StratX Quant Skill 14: Research Exhaustion Engine
Enforces software-governed proof of FAMILY_EXHAUSTED. Prevents subjective stopping.
Evaluates hypothesis coverage, plateau surveys, and remaining EIV against exhaustion thresholds.
"""

from typing import Dict, Any, List, Optional

class ResearchExhaustionEngine:
    def __init__(self, min_hypotheses_tested: int = 3, min_branches_tested: int = 4, eiv_exhaustion_floor: float = 0.25):
        self.min_hypotheses_tested = min_hypotheses_tested
        self.min_branches_tested = min_branches_tested
        self.eiv_exhaustion_floor = eiv_exhaustion_floor

    def evaluate_family_exhaustion(self, family_name: str, family_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines whether a strategy family has genuinely reached exhaustion within tested scope.
        """
        hypotheses_count = int(family_evidence.get("hypotheses_tested_count", 0))
        branches_count = int(family_evidence.get("branches_tested_count", 0))
        remaining_eiv = float(family_evidence.get("remaining_eiv", 0.5))
        val_status = str(family_evidence.get("val_status", "UNKNOWN"))
        parameter_sweeps_done = bool(family_evidence.get("parameter_sweeps_completed", False))

        is_exhausted = False
        reasons = []

        if hypotheses_count < self.min_hypotheses_tested:
            reasons.append(f"Insufficient hypotheses tested ({hypotheses_count}/{self.min_hypotheses_tested}).")
        if branches_count < self.min_branches_tested:
            reasons.append(f"Insufficient experimental branches explored ({branches_count}/{self.min_branches_tested}).")
        if not parameter_sweeps_done:
            reasons.append("Parameter neighborhood sweeps not completed.")

        if not reasons and remaining_eiv <= self.eiv_exhaustion_floor and val_status in ["REFUTED", "OVERFIT_COLLAPSE"]:
            is_exhausted = True

        status = "FAMILY_EXHAUSTED_WITHIN_DEFINED_SCOPE" if is_exhausted else "RESEARCH_ACTIVE"

        return {
            "family_name": family_name,
            "status": status,
            "is_exhausted": is_exhausted,
            "remaining_eiv": remaining_eiv,
            "hypotheses_tested": hypotheses_count,
            "branches_tested": branches_count,
            "unfulfilled_criteria": reasons,
            "recommendation": "DEPRIORITISE_FAMILY_AND_ADVANCE_PORTFOLIO_QUEUE" if is_exhausted else "CONTINUE_SELF_HEALING_BRANCHES"
        }
