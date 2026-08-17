"""
StratX Quant Skill 18: Tripartite Memory & Pre-Compute Proposal Gate Engine
Implements:
1. Rich Contextual Memory Model (Strategy Memory, Belief Memory, Research Policy Memory).
2. Mandatory Iteration Memory Commitment Invariant (blocks closing iteration if memory uncommitted).
3. Pre-Compute Proposal Gate (Duplicate check, FAILED_IN_CONTEXT justification, Policy compliance).
4. Auditable Memory Provenance Citation (MEMORY_USED + HOW_THEY_CHANGED_THIS_DECISION).
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid
import json

class TripartiteMemoryEngine:

    def create_rich_memory_record(
        self,
        mission_id: str,
        goal_id: str,
        iteration_id: int,
        failure_signature: Dict[str, Any],
        belief_before: str,
        hypothesis_id: str,
        experiment_id: str,
        intervention: Dict[str, Any],
        predicted_outcome: Dict[str, Any],
        actual_outcome: Dict[str, Any],
        child_parent_delta: Dict[str, Any],
        belief_status: str,
        confidence_delta: float,
        strategy_lesson: str,
        research_method_lesson: str,
        future_trigger: str,
        future_behavior: str,
        source_report_hash: str = "HASH_VERIFIED",
        confidence: float = 0.85
    ) -> Dict[str, Any]:
        mem_id = f"MEM_{uuid.uuid4().hex[:8].upper()}"

        return {
            "memory_id": mem_id,
            "mission_id": mission_id,
            "self_review_goal_id": goal_id,
            "iteration_id": iteration_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "failure_signature": failure_signature,
            "belief_before": belief_before,
            "hypothesis_id": hypothesis_id,
            "experiment_id": experiment_id,
            "intervention": intervention,
            "predicted_outcome": predicted_outcome,
            "actual_outcome": actual_outcome,
            "child_parent_delta": child_parent_delta,
            "belief_after": {
                "status": belief_status,
                "confidence_delta": round(confidence_delta, 4)
            },
            "experiment_verdict": f"HYPOTHESIS_{belief_status}",
            "strategy_lesson": strategy_lesson,
            "research_method_lesson": research_method_lesson,
            "future_trigger": future_trigger,
            "future_behavior": future_behavior,
            "evidence_level": "VALIDATION",
            "source_report_hash": source_report_hash,
            "confidence": round(confidence, 4),
            "memory_types_committed": ["STRATEGY_MEMORY", "BELIEF_MEMORY", "RESEARCH_POLICY_MEMORY"]
        }

    def evaluate_pre_compute_proposal_gate(
        self,
        proposed_spec: Dict[str, Any],
        prior_memories: List[Dict[str, Any]],
        retrieved_policies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        rejection_reasons = []
        warnings = []
        is_repeat = False

        spec_params = proposed_spec.get("parameter_changes", {})
        spec_desc = proposed_spec.get("description", "")
        spec_justification = proposed_spec.get("repeat_justification")
        spec_context_diff = proposed_spec.get("material_context_difference")

        # 1. Check against prior FAILED_IN_CONTEXT memories
        for mem in prior_memories:
            prior_interv = mem.get("intervention", {})
            prior_verdict = mem.get("experiment_verdict", "")
            prior_desc = prior_interv.get("description", "")
            prior_params = prior_interv.get("parameter_changes", {})
            
            # Check non-empty exact matches
            desc_match = bool(spec_desc and prior_desc and spec_desc == prior_desc)
            param_match = bool(spec_params and prior_params and spec_params == prior_params)

            if desc_match or param_match:
                if "REFUTED" in prior_verdict or "NOT_SUPPORTED" in prior_verdict or "WEAKENED" in prior_verdict:
                    is_repeat = True
                    if not (spec_justification and spec_context_diff):
                        rejection_reasons.append(
                            f"DUPLICATE_LOW_EIV: Experiment matches failed attempt {mem.get('experiment_id')} ({prior_verdict}) without REPEAT_JUSTIFICATION or MATERIAL_CONTEXT_DIFFERENCE."
                        )

        # 2. Check against Policy Memory rules
        for pol in retrieved_policies:
            rec_beh = pol.get("recommended_behavior", pol.get("recommended_future_behavior", ""))
            if "PREFER_SINGLE_CAUSAL_GATES" in rec_beh and len(spec_params) > 2:
                rejection_reasons.append(
                    f"POLICY_VIOLATION ({pol.get('policy_id')}): Proposed experiment stacks {len(spec_params)} parameters, violating single-causal gate policy."
                )

        # 3. Check Memory Citation
        memory_used = proposed_spec.get("memory_used", [])
        memory_reasoning = proposed_spec.get("how_memory_changed_decision", "")

        if prior_memories and not memory_used:
            rejection_reasons.append("PROVENANCE_ERROR: No prior MEMORY_USED cited in experiment specification.")
        elif memory_used and not memory_reasoning:
            rejection_reasons.append("PROVENANCE_ERROR: MEMORY_USED cited but HOW_THEY_CHANGED_THIS_DECISION is missing.")

        is_approved = (len(rejection_reasons) == 0)

        return {
            "status": "APPROVED" if is_approved else "EXPERIMENT_REJECTED_BEFORE_COMPUTE",
            "is_approved": is_approved,
            "rejection_reasons": rejection_reasons,
            "warnings": warnings,
            "is_repeat_with_justification": bool(is_repeat and is_approved),
            "cited_memory_count": len(memory_used)
        }

    def validate_iteration_memory_commitment_invariant(
        self,
        memory_record: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not memory_record:
            return {
                "is_valid": False,
                "status": "ITERATION_CLOSE_BLOCKED",
                "error": "MANDATORY_MEMORY_COMMIT_MISSING: Iteration cannot close without a committed memory record."
            }

        committed = memory_record.get("memory_types_committed", [])
        required = ["STRATEGY_MEMORY", "BELIEF_MEMORY", "RESEARCH_POLICY_MEMORY"]

        missing = [r for r in required if r not in committed]
        if missing:
            return {
                "is_valid": False,
                "status": "ITERATION_CLOSE_BLOCKED",
                "error": f"INCOMPLETE_MEMORY_COMMIT: Missing {missing} in memory record."
            }

        return {
            "is_valid": True,
            "status": "MEMORY_COMMIT_VERIFIED",
            "memory_id": memory_record.get("memory_id")
        }
