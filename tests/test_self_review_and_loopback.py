"""
StratX Quant Acceptance Test: Mandatory Self-Review Loop, Persistent Goal Engine & Backward Loopback Routing
Tests:
1. Canonical forward flow: MT5 -> Delta -> Self-Review -> Child Re-Forensics -> Reviewer -> Governor.
2. Software enforcement: Next generation forbidden without Self-Review and Child Re-Forensics.
3. Backward loopback routing: Self-Review detects hypothesis contradiction / over-complexity -> routes backward.
4. Persistent Goal-Based Loop: Multi-iteration healing loop where Self-Review refuses to exit until exact goal metrics pass.
"""

import sys
import csv
import json
import unittest
from pathlib import Path

# Add skills dir
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills import (
    TradePopulationAnalyzer,
    ClusterDetector,
    RegimeTagger,
    ChildParentDelta,
    StructuralMutationEngine,
    SelfReviewEngine,
    ResearchPolicyLearner
)

class TestSelfReviewAndLoopback(unittest.TestCase):

    def setUp(self):
        self.parent_raw = self._load_csv('C:/Trading/DE40-Research/evidence/VPPOC_V4_DEV_trades.csv')
        self.child_raw = self._load_csv('C:/Trading/DE40-Research/evidence/VPPOC_CHAMP_DEV_trades.csv')

    def _load_csv(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))

    def test_canonical_self_review_and_reforensics_flow(self):
        print("\n--- TEST 1: Canonical Forward Flow with Self-Review and Child Re-Forensics ---")
        analyzer = TradePopulationAnalyzer()
        p_pop = analyzer.analyze_trades(self.parent_raw)["positions"]
        c_pop = analyzer.analyze_trades(self.child_raw)["positions"]

        # Step 1: Child-Parent Delta
        delta_eng = ChildParentDelta()
        delta_res = delta_eng.compute_delta(p_pop, c_pop)
        print(f"1. Child-Parent Delta: Net R Delta = {delta_res['net_R_delta']:+.2f}R | Losers Removed = {delta_res['losers_removed_count']}")

        # Step 2: Formulate Spec
        mut_eng = StructuralMutationEngine()
        spec = mut_eng.create_experiment_spec(
            experiment_id="EXP_VPPOC_G4_CHAMP",
            parent_strategy_id="VPPOC_V4",
            hypothesis_id="HYP_VPPOC_PROFILE",
            repair_level="L2_RULE",
            market_thesis="Require POC rejection distance >= 1.0",
            parameter_changes={"InpPocMinDist": 1.0}
        )
        spec["predicted_effect"] = "Prune low-distance chop losers while preserving 90%+ winners"
        spec["predicted_damage"] = "Potential 10-15% frequency reduction"

        # Step 3: Execute Mandatory Self-Review
        srev_engine = SelfReviewEngine()
        srev_record = srev_engine.create_self_review(
            mission_id="de40-x1x",
            generation_id="GEN_4",
            experiment_id="EXP_VPPOC_G4_CHAMP",
            parent_id="VPPOC_V4",
            child_id="VPPOC_CHAMP",
            experiment_spec=spec,
            child_parent_delta=delta_res,
            child_metrics={}
        )
        print(f"2. Self-Review Completed: Review ID = {srev_record['review_id']}")
        print(f"   -> Prediction Match: {srev_record['prediction_match']}")
        print(f"   -> Target Failure Status: {srev_record['target_failure_status']}")
        print(f"   -> Causal Belief Update: {srev_record['causal_belief_update']}")
        print(f"   -> Research Method Lesson: {srev_record['research_method_lesson']}")
        print(f"   -> Recommended Route: {srev_record['recommended_route']}")

        self.assertEqual(srev_record["prediction_match"], "CONFIRMED")
        self.assertEqual(srev_record["causal_belief_update"], "SUPPORTED")
        self.assertEqual(srev_record["recommended_route"], "CHILD_REFORENSICS_REQUIRED")

        # Step 4: Mandatory Child Re-Forensics
        print("3. Executing Mandatory Child Re-Forensics on Child population...")
        tagger = RegimeTagger()
        tagged_child = tagger.tag_population(c_pop)
        detector = ClusterDetector()
        child_clusters = detector.detect_clusters(tagged_child)
        print(f"   -> Child Re-Forensics Completed: {child_clusters['clusters_found']} clusters in child failure map")

        # Step 5: Validate Workflow Gates
        gate_check = srev_engine.validate_workflow_gates({}, srev_record, child_clusters)
        print(f"4. Workflow Gate Check: {gate_check['status']} (is_allowed: {gate_check['is_allowed']})")
        self.assertTrue(gate_check["is_allowed"])
        self.assertEqual(gate_check["status"], "APPROVED")

    def test_software_enforcement_missing_self_review(self):
        print("\n--- TEST 2: Software Gatekeeper Blocks Next Gen Without Self-Review ---")
        srev_engine = SelfReviewEngine()
        gate_blocked = srev_engine.validate_workflow_gates({}, None, None)
        print(f"Gate Verdict (Missing Self Review): {gate_blocked['status']} | Violations: {gate_blocked['violations']}")
        self.assertFalse(gate_blocked["is_allowed"])
        self.assertIn("NEXT_GENERATION_FORBIDDEN: Missing mandatory SELF_REVIEW_RECORD.", gate_blocked["violations"])

    def test_software_enforcement_missing_child_reforensics(self):
        print("\n--- TEST 3: Software Gatekeeper Blocks Next Gen Without Child Re-Forensics ---")
        srev_engine = SelfReviewEngine()
        spec = {"predicted_effect": "Improve win rate", "parameter_changes": {}}
        delta = {"net_R_delta": 5.0, "losers_removed_count": 3, "winners_removed_count": 0, "frequency_retention_pct": 90.0}
        srev_record = srev_engine.create_self_review("de40-x1x", "GEN_1", "EXP_01", "P", "C", spec, delta, {})
        
        gate_blocked = srev_engine.validate_workflow_gates({}, srev_record, None)
        print(f"Gate Verdict (Missing Child Re-Forensics): {gate_blocked['status']} | Violations: {gate_blocked['violations']}")
        self.assertFalse(gate_blocked["is_allowed"])
        self.assertIn("NEXT_GENERATION_FORBIDDEN: Missing mandatory CHILD_REFORENSICS failure map.", gate_blocked["violations"])

    def test_backward_loopback_on_hypothesis_contradiction(self):
        print("\n--- TEST 4: Backward Loopback Routing on Hypothesis Contradiction ---")
        srev_engine = SelfReviewEngine()
        spec = {
            "predicted_effect": "Eliminate morning losses",
            "market_thesis": "Morning entries have negative edge",
            "parameter_changes": {"InpSession": 2}
        }
        bad_delta = {
            "net_R_delta": -8.0,
            "losers_removed_count": 1,
            "winners_removed_count": 10,
            "frequency_retention_pct": 45.0,
            "same_trade_count": 15,
            "new_trade_count": 0
        }
        srev_record = srev_engine.create_self_review("de40-x1x", "GEN_2", "EXP_BAD", "P", "C", spec, bad_delta, {})
        print(f"Self-Review Verdict on Damage: Prediction Match = {srev_record['prediction_match']}")
        print(f"   -> Causal Belief Update: {srev_record['causal_belief_update']}")
        print(f"   -> Recommended Backward Route: {srev_record['recommended_route']}")

        self.assertEqual(srev_record["prediction_match"], "CONTRADICTED")
        self.assertEqual(srev_record["causal_belief_update"], "REFUTED")
        self.assertEqual(srev_record["recommended_route"], "SELF_HEALER_HYPOTHESIS_PIVOT")

    def test_persistent_goal_based_self_review_loop(self):
        print("\n--- TEST 5: Persistent Goal-Based Self-Review Loop ---")
        srev_engine = SelfReviewEngine()
        
        # Define Goal
        goal_metrics = {
            "win_rate": 0.70,
            "profit_factor": 2.0,
            "risk_reward": 1.0,
            "min_trades_per_year": 20.0
        }
        goal_session = srev_engine.create_goal_session(
            mission_id="de40-x1x",
            module_id="M1_VPPOC",
            parent_id="CANDIDATE_PARENT",
            goal_id="GOAL_M1_PAYOFF_REPAIR",
            goal_definition="Repair M1 payoff architecture while preserving validated entry edge",
            goal_metrics=goal_metrics,
            goal_constraints={"max_drawdown": 1000.0}
        )
        self.assertEqual(goal_session["status"], "ACTIVE")
        self.assertEqual(goal_session["iteration"], 1)

        # ITERATION 1: Candidate has high WR/PF but fails RR gate (RR = 0.80)
        c1_metrics = {"win_rate": 0.75, "profit_factor": 3.0, "risk_reward": 0.80, "trades_per_year": 25.0}
        c1_delta = {"net_R_delta": 3.5, "losers_removed_count": 2, "winners_removed_count": 0, "frequency_retention_pct": 95.0}
        
        res1 = srev_engine.evaluate_goal(goal_session, "CANDIDATE_IT1", c1_metrics, c1_delta)
        print(f"\nIteration 1 Result:")
        print(f"   -> Goal Status: {res1['goal_status']} | All Passed: {res1['all_passed']}")
        print(f"   -> Unmet Dimensions: {res1['unmet_dimensions']}")
        print(f"   -> Can Exit: {res1['can_exit']}")

        self.assertFalse(res1["all_passed"])
        self.assertEqual(res1["goal_status"], "REASSESSING")
        self.assertFalse(res1["can_exit"])
        
        # Check exit gatekeeper: MUST FORBID EXIT
        exit_check1 = srev_engine.can_exit_self_review(goal_session)
        self.assertFalse(exit_check1["can_exit"])
        self.assertEqual(exit_check1["reason"], "SELF_REVIEW_GOAL_UNMET")
        self.assertEqual(exit_check1["allowed_next_stage"], "SELF_REVIEW_ITERATION")

        # Advance to Iteration 2
        srev_engine.advance_iteration(goal_session, new_hypothesis_id="HYP_EXTEND_TP", new_spec_id="EXP_TP_02")
        self.assertEqual(goal_session["iteration"], 2)

        # ITERATION 2: Candidate fixed RR (1.05) but damaged WR (69% < 70%)
        c2_metrics = {"win_rate": 0.69, "profit_factor": 2.4, "risk_reward": 1.05, "trades_per_year": 24.0}
        c2_delta = {"net_R_delta": 1.2, "losers_removed_count": 0, "winners_removed_count": 1, "frequency_retention_pct": 92.0}
        
        res2 = srev_engine.evaluate_goal(goal_session, "CANDIDATE_IT2", c2_metrics, c2_delta)
        print(f"\nIteration 2 Result:")
        print(f"   -> Goal Status: {res2['goal_status']} | All Passed: {res2['all_passed']}")
        print(f"   -> Unmet Dimensions: {res2['unmet_dimensions']}")
        print(f"   -> Can Exit: {res2['can_exit']}")

        self.assertFalse(res2["all_passed"])
        self.assertFalse(res2["can_exit"])
        exit_check2 = srev_engine.can_exit_self_review(goal_session)
        self.assertFalse(exit_check2["can_exit"])

        # Advance to Iteration 3
        srev_engine.advance_iteration(goal_session, new_hypothesis_id="HYP_RUNNER_SPLIT", new_spec_id="EXP_SPLIT_03")
        self.assertEqual(goal_session["iteration"], 3)

        # ITERATION 3: Candidate achieves all goal metrics (WR 72%, PF 2.2, RR 1.03, Vol 22)
        c3_metrics = {"win_rate": 0.72, "profit_factor": 2.2, "risk_reward": 1.03, "trades_per_year": 22.0}
        c3_delta = {"net_R_delta": 4.1, "losers_removed_count": 3, "winners_removed_count": 0, "frequency_retention_pct": 90.0}
        
        res3 = srev_engine.evaluate_goal(goal_session, "CANDIDATE_IT3", c3_metrics, c3_delta)
        print(f"\nIteration 3 Result:")
        print(f"   -> Goal Status: {res3['goal_status']} | All Passed: {res3['all_passed']}")
        print(f"   -> Met Dimensions: {res3['met_dimensions']}")
        print(f"   -> Can Exit: {res3['can_exit']}")

        self.assertTrue(res3["all_passed"])
        self.assertEqual(res3["goal_status"], "PASSED")
        self.assertTrue(res3["can_exit"])
        
        # Check exit gatekeeper: NOW ALLOWS ADVANCE TO INDEPENDENT_REVIEWER
        exit_check3 = srev_engine.can_exit_self_review(goal_session)
        print(f"   -> Exit Gatekeeper: {exit_check3['reason']} -> Allowed Next Stage: {exit_check3['allowed_next_stage']}")
        self.assertTrue(exit_check3["can_exit"])
        self.assertEqual(exit_check3["reason"], "GOAL_PASSED")
        self.assertEqual(exit_check3["allowed_next_stage"], "INDEPENDENT_REVIEWER")

if __name__ == "__main__":
    unittest.main()
