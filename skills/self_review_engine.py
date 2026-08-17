"""
StratX Quant Skill 17: Persistent Goal-Based Self-Review & Healing Loop Engine
Implements the persistent, goal-oriented Self-Review state machine:
- Goal-based evaluation (completing todos != passing self-review).
- Iteration management with state persistence.
- Deterministic can_exit_self_review() gatekeeper.
- Escalation & exhaustion handling without silent goal weakening.
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid
import json

class SelfReviewEngine:
    ALLOWED_STATUSES = ["ACTIVE", "TESTING", "REASSESSING", "PASSED", "ESCALATE", "BLOCKED"]
    VALID_PREDICTION_MATCHES = ["CONFIRMED", "PARTIAL", "CONTRADICTED", "INCONCLUSIVE"]
    VALID_TARGET_STATUSES = ["FIXED", "IMPROVED", "UNCHANGED", "WORSE", "UNKNOWN"]
    VALID_BELIEF_UPDATES = ["SUPPORTED", "WEAKENED", "REFUTED", "UNCHANGED", "REOPEN"]

    def create_goal_session(
        self,
        mission_id: str,
        module_id: str,
        parent_id: str,
        goal_id: str,
        goal_definition: str,
        goal_metrics: Dict[str, float],
        goal_constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initializes a persistent goal-driven Self-Review session.
        """
        review_id = f"SREV_{uuid.uuid4().hex[:8].upper()}"
        return {
            "self_review_id": review_id,
            "mission_id": mission_id,
            "module_id": module_id,
            "parent_id": parent_id,
            "current_candidate_id": parent_id,
            "goal_id": goal_id,
            "goal_definition": goal_definition,
            "goal_metrics": goal_metrics, # e.g. {"win_rate": 0.70, "profit_factor": 2.0, "risk_reward": 1.0, "min_trades_per_year": 20.0}
            "goal_constraints": goal_constraints, # e.g. {"max_drawdown": 1000.0, "validation_integrity": True}
            "goal_status": "ACTIVE",
            "status": "ACTIVE", # MUST NEVER BE 'DONE'
            "iteration": 1,
            "history": [],
            "current_failure_map": [],
            "current_hypothesis_ids": [],
            "current_experiment_ids": [],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    def evaluate_goal(
        self,
        session: Dict[str, Any],
        candidate_id: str,
        candidate_metrics: Dict[str, Any],
        child_parent_delta: Dict[str, Any],
        validation_audit: Optional[Dict[str, Any]] = None,
        spec: Optional[Dict[str, Any]] = None,
        receipt: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compares the candidate against the immutable goal metrics & constraints.
        Returns detailed pass/fail dimensions, reasons, and next state.
        """
        target_metrics = session.get("goal_metrics", {})
        constraints = session.get("goal_constraints", {})

        unmet_dimensions = []
        met_dimensions = []

        # 1. Evaluate Metrics
        c_wr = float(candidate_metrics.get("win_rate", 0.0))
        c_pf = float(candidate_metrics.get("profit_factor", 0.0))
        c_rr = float(candidate_metrics.get("payoff_ratio", candidate_metrics.get("risk_reward", 0.0)))
        c_trades = float(candidate_metrics.get("trade_count", candidate_metrics.get("trades", 0)))
        c_trades_yr = float(candidate_metrics.get("trades_per_year", c_trades))

        if "win_rate" in target_metrics:
            req_wr = target_metrics["win_rate"]
            if c_wr >= req_wr - 1e-4:
                met_dimensions.append(f"Win Rate: {c_wr*100:.1f}% >= {req_wr*100:.1f}%")
            else:
                unmet_dimensions.append(f"Win Rate: {c_wr*100:.1f}% < {req_wr*100:.1f}% (Deficit: {(req_wr - c_wr)*100:.1f}%)")

        if "profit_factor" in target_metrics:
            req_pf = target_metrics["profit_factor"]
            if c_pf >= req_pf - 1e-4:
                met_dimensions.append(f"Profit Factor: {c_pf:.2f} >= {req_pf:.2f}")
            else:
                unmet_dimensions.append(f"Profit Factor: {c_pf:.2f} < {req_pf:.2f} (Deficit: {req_pf - c_pf:.2f})")

        if "risk_reward" in target_metrics or "payoff_ratio" in target_metrics:
            req_rr = target_metrics.get("risk_reward", target_metrics.get("payoff_ratio", 1.0))
            if c_rr >= req_rr - 1e-4:
                met_dimensions.append(f"Risk/Reward: {c_rr:.2f} >= {req_rr:.2f}")
            else:
                unmet_dimensions.append(f"Risk/Reward: {c_rr:.2f} < {req_rr:.2f} (Deficit: {req_rr - c_rr:.2f})")

        if "min_trades_per_year" in target_metrics:
            req_tr = target_metrics["min_trades_per_year"]
            if c_trades_yr >= req_tr:
                met_dimensions.append(f"Trades/Year: {c_trades_yr:.1f} >= {req_tr:.1f}")
            else:
                unmet_dimensions.append(f"Trades/Year: {c_trades_yr:.1f} < {req_tr:.1f} (Volume deficit)")

        # 2. Evaluate Constraints
        c_dd = float(candidate_metrics.get("max_drawdown", candidate_metrics.get("equity_dd", 0.0)))
        if "max_drawdown" in constraints and c_dd > constraints["max_drawdown"]:
            unmet_dimensions.append(f"Drawdown breach: {c_dd:.1f} > max allowed {constraints['max_drawdown']}")

        if validation_audit and not validation_audit.get("passed_generalization", True):
            unmet_dimensions.append(f"Validation failure: {validation_audit.get('verdict', 'OUT_OF_SAMPLE_COLLAPSE')}")

        if receipt and not receipt.get("compile_success", True):
            unmet_dimensions.append("Implementation failure: MQL5 compile error")

        # 3. Determine Goal Status
        all_passed = (len(unmet_dimensions) == 0)
        goal_status = "PASSED" if all_passed else "REASSESSING"

        # 4. Generate 14-point review record for this iteration
        review_record = self.create_self_review(
            mission_id=session.get("mission_id", "de40-x1x"),
            generation_id=f"GEN_{session.get('iteration', 1)}",
            experiment_id=spec.get("experiment_id", f"EXP_IT{session.get('iteration', 1)}") if spec else f"EXP_IT{session.get('iteration', 1)}",
            parent_id=session.get("parent_id", "PARENT"),
            child_id=candidate_id,
            experiment_spec=spec or {"predicted_effect": "Pass goal", "market_thesis": "Heal strategy"},
            child_parent_delta=child_parent_delta,
            child_metrics=candidate_metrics,
            implementation_receipt=receipt
        )

        iteration_entry = {
            "iteration": session.get("iteration", 1),
            "candidate_id": candidate_id,
            "goal_status": goal_status,
            "all_passed": all_passed,
            "met_dimensions": met_dimensions,
            "unmet_dimensions": unmet_dimensions,
            "review_record": review_record,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Update session state
        session["current_candidate_id"] = candidate_id
        session["goal_status"] = goal_status
        session["status"] = goal_status # PASSED or REASSESSING/ACTIVE
        session["history"].append(iteration_entry)
        session["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return {
            "self_review_id": session.get("self_review_id"),
            "iteration": session.get("iteration", 1),
            "goal_id": session.get("goal_id"),
            "goal_status": goal_status,
            "all_passed": all_passed,
            "met_dimensions": met_dimensions,
            "unmet_dimensions": unmet_dimensions,
            "can_exit": all_passed,
            "review_record": review_record,
            "recommended_action": "PROCEED_TO_INDEPENDENT_REVIEW" if all_passed else "EXECUTE_NEXT_HEALING_ITERATION"
        }

    def can_exit_self_review(self, session: Dict[str, Any], genuine_blocker: bool = False, is_exhausted: bool = False) -> Dict[str, Any]:
        """
        Deterministic Exit Gatekeeper:
        Forbids leaving SELF_REVIEW stage unless goal_status == 'PASSED',
        a genuine external blocker exists, or research is proven exhausted.
        """
        if not session:
            return {"can_exit": False, "reason": "NO_SELF_REVIEW_SESSION", "allowed_next_stage": "SELF_REVIEW"}

        goal_status = session.get("goal_status", "ACTIVE")

        if goal_status == "PASSED":
            return {
                "can_exit": True,
                "reason": "GOAL_PASSED",
                "allowed_next_stage": "INDEPENDENT_REVIEWER",
                "instruction": "Self-review passed all goal metrics and constraints. Advance to Independent Adversarial Review."
            }

        if genuine_blocker:
            session["status"] = "BLOCKED"
            session["goal_status"] = "BLOCKED"
            return {
                "can_exit": True,
                "reason": "GENUINE_EXTERNAL_BLOCKER",
                "allowed_next_stage": "BLOCKED",
                "instruction": "External physical blocker encountered (e.g. disk/API error)."
            }

        if is_exhausted or goal_status == "ESCALATE":
            session["status"] = "ESCALATE"
            return {
                "can_exit": True,
                "reason": "RESEARCH_EXHAUSTION_ESCALATION",
                "allowed_next_stage": "SUPERVISOR_GOVERNOR_ESCALATION",
                "instruction": "Current research repair level exhausted. Escalate to Head Quant / Governor."
            }

        # GOAL UNMET: FORBID EXIT
        return {
            "can_exit": False,
            "reason": "SELF_REVIEW_GOAL_UNMET",
            "allowed_next_stage": "SELF_REVIEW_ITERATION",
            "iteration": session.get("iteration", 1),
            "unmet_dimensions": session.get("history", [{}])[-1].get("unmet_dimensions", []) if session.get("history") else [],
            "instruction": "FORBIDDEN to exit SELF_REVIEW. Goal metrics unmet. Advance to next healing iteration."
        }

    def advance_iteration(self, session: Dict[str, Any], new_hypothesis_id: Optional[str] = None, new_spec_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Increments iteration counter and prepares session for next self-healing cycle.
        """
        session["iteration"] = session.get("iteration", 1) + 1
        session["status"] = "ACTIVE"
        session["goal_status"] = "ACTIVE"
        if new_hypothesis_id:
            session["current_hypothesis_ids"].append(new_hypothesis_id)
        if new_spec_id:
            session["current_experiment_ids"].append(new_spec_id)
        session["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return session

    def create_self_review(
        self,
        mission_id: str,
        generation_id: str,
        experiment_id: str,
        parent_id: str,
        child_id: str,
        experiment_spec: Dict[str, Any],
        child_parent_delta: Dict[str, Any],
        child_metrics: Dict[str, Any],
        implementation_receipt: Optional[Dict[str, Any]] = None,
        previous_policy_memory: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generates canonical 14-point review record.
        """
        pred_effect = experiment_spec.get("predicted_effect", "Unknown prediction")
        pred_damage = experiment_spec.get("predicted_damage", "Unknown damage risk")

        net_r_delta = float(child_parent_delta.get("net_R_delta", 0.0))
        losers_rem = int(child_parent_delta.get("losers_removed_count", 0))
        winners_rem = int(child_parent_delta.get("winners_removed_count", 0))
        freq_retention = float(child_parent_delta.get("frequency_retention_pct", 100.0))
        same_count = int(child_parent_delta.get("same_trade_count", 0))
        new_count = int(child_parent_delta.get("new_trade_count", 0))

        impl_fid = "MATCH"
        if implementation_receipt:
            if not implementation_receipt.get("compile_success", True):
                impl_fid = "MISMATCH"
            elif implementation_receipt.get("mismatches"):
                impl_fid = "MISMATCH" if len(implementation_receipt.get("mismatches", [])) > 1 else "PARTIAL"

        if net_r_delta < -2.0 or (winners_rem > losers_rem * 2 and net_r_delta < 0):
            pred_match = "CONTRADICTED"
        elif net_r_delta > 2.0 or (losers_rem > winners_rem and net_r_delta > 0):
            pred_match = "CONFIRMED"
        elif net_r_delta > 0.0 or losers_rem > 0:
            pred_match = "PARTIAL"
        else:
            pred_match = "INCONCLUSIVE"

        if net_r_delta > 2.0 and (losers_rem >= winners_rem or new_count > 0):
            target_status = "IMPROVED" if winners_rem > 0 else "FIXED"
        elif losers_rem > winners_rem:
            target_status = "IMPROVED"
        elif net_r_delta < -1.0 or winners_rem > losers_rem * 2:
            target_status = "WORSE"
        elif losers_rem == 0 and winners_rem == 0:
            target_status = "UNCHANGED"
        else:
            target_status = "IMPROVED" if net_r_delta > 0 else "UNKNOWN"

        new_failures = []
        damaged_dims = []
        improved_dims = []

        if winners_rem > 0:
            damaged_dims.append(f"Pruned {winners_rem} high-value winning trades")
        if freq_retention < 60.0:
            damaged_dims.append(f"Frequency collapse: {100.0 - freq_retention:.1f}% trade volume dropped")
            new_failures.append("FREQUENCY_COLLAPSE")

        if losers_rem > 0:
            improved_dims.append(f"Eliminated {losers_rem} unprofitable trades")
        if net_r_delta > 0:
            improved_dims.append(f"Net expectancy increased by +{net_r_delta:.2f}R")
        if new_count > 0:
            improved_dims.append(f"Captured {new_count} new valid alpha trade opportunities")

        if pred_match == "CONFIRMED":
            belief_update = "SUPPORTED"
        elif pred_match == "PARTIAL":
            belief_update = "UNCHANGED"
        elif pred_match == "CONTRADICTED":
            belief_update = "REFUTED"
        else:
            belief_update = "WEAKENED"

        param_changes = experiment_spec.get("parameter_changes", {})
        if len(param_changes) <= 2:
            design_quality = "VALID"
        elif len(param_changes) <= 4:
            design_quality = "WEAK"
        else:
            design_quality = "INVALID"

        if pred_match == "CONFIRMED":
            strat_lesson = f"Strategy alpha holds: {experiment_spec.get('market_thesis', 'Isolated regime filter')} is empirically valid."
            res_lesson = "Single well-isolated causal feature effectively prunes bad trade cohort without collateral damage."
            rec_route = "CHILD_REFORENSICS_REQUIRED"
        elif impl_fid == "MISMATCH":
            strat_lesson = "Execution failed at MQL5 code level; no valid strategy conclusion can be drawn."
            res_lesson = "MQL5 compiler or parameter synchronization failed before backtest."
            rec_route = "MQL5_ARCHITECT"
        elif design_quality == "INVALID":
            strat_lesson = "Multiple simultaneous mutations confounded trade attribution."
            res_lesson = "Ablate multi-parameter changes into independent single-variable branch experiments."
            rec_route = "EXPERIMENT_PLANNER"
        elif pred_match == "CONTRADICTED":
            strat_lesson = f"Hypothesis refutation: {experiment_spec.get('market_thesis', 'Proposed filter')} destroyed high-expectancy trades."
            res_lesson = "Filter accretion on this feature causes out-of-sample damage. Pivot to entry timing or stop architecture."
            rec_route = "SELF_HEALER_HYPOTHESIS_PIVOT"
        else:
            strat_lesson = "Marginal trade shift; feature lacks decisive causal edge."
            res_lesson = "Survey parameter neighborhood or test alternative volatility normalization."
            rec_route = "CHILD_REFORENSICS_REQUIRED"

        review_id = f"REV_{uuid.uuid4().hex[:8].upper()}"

        return {
            "review_id": review_id,
            "mission_id": mission_id,
            "generation_id": generation_id,
            "experiment_id": experiment_id,
            "parent_id": parent_id,
            "child_id": child_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "predicted_outcome": {
                "predicted_effect": pred_effect,
                "predicted_damage": pred_damage
            },
            "observed_outcome": {
                "net_R_delta": round(net_r_delta, 4),
                "losers_removed": losers_rem,
                "winners_removed": winners_rem,
                "frequency_retention_pct": round(freq_retention, 2),
                "same_trades": same_count,
                "new_trades": new_count
            },
            "prediction_match": pred_match,
            "target_failure_status": target_status,
            "new_failure_families": new_failures,
            "improved_dimensions": improved_dims,
            "damaged_dimensions": damaged_dims,
            "causal_belief_update": belief_update,
            "experiment_design_quality": design_quality,
            "implementation_fidelity": impl_fid,
            "unexpected_findings": [] if pred_match == "CONFIRMED" else [f"Observed R delta {net_r_delta:+.2f}R diverged from predicted benefit"],
            "strategy_lesson": strat_lesson,
            "research_method_lesson": res_lesson,
            "recommended_route": rec_route,
            "workflow_gates": {
                "self_review_completed": True,
                "child_reforensics_required": bool(rec_route == "CHILD_REFORENSICS_REQUIRED"),
                "child_reforensics_completed": False
            }
        }

    def validate_workflow_gates(self, state: Dict[str, Any], self_review_record: Optional[Dict[str, Any]], child_reforensics_record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        violations = []

        if not self_review_record:
            violations.append("NEXT_GENERATION_FORBIDDEN: Missing mandatory SELF_REVIEW_RECORD.")

        if self_review_record:
            impl_fid = self_review_record.get("implementation_fidelity")
            if impl_fid == "MISMATCH":
                violations.append("NEXT_GENERATION_FORBIDDEN: Implementation mismatch detected. Route back to MQL5_ARCHITECT.")

            design_q = self_review_record.get("experiment_design_quality")
            if design_q == "INVALID":
                violations.append("NEXT_GENERATION_FORBIDDEN: Invalid multi-variable experiment design. Route back to EXPERIMENT_PLANNER.")

            if not child_reforensics_record and self_review_record.get("recommended_route") == "CHILD_REFORENSICS_REQUIRED":
                violations.append("NEXT_GENERATION_FORBIDDEN: Missing mandatory CHILD_REFORENSICS failure map.")

        is_allowed = (len(violations) == 0)

        return {
            "status": "APPROVED" if is_allowed else "WORKFLOW_GATE_BLOCKED",
            "is_allowed": is_allowed,
            "violations": violations,
            "recommended_action": "PROCEED_TO_INDEPENDENT_REVIEW" if is_allowed else (violations[0] if violations else "HOLD")
        }
