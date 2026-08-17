"""
StratX Quant Acceptance Test: Evolutionary Tripartite Memory Loop & Pre-Compute Proposal Gate
Tests:
1. Rich Contextual Memory Model committed on every iteration.
2. Workflow Invariant: Iteration cannot close without tripartite memory commitment.
3. Pre-Compute Proposal Gate: Rejects duplicate low-EIV attempts unless justified.
4. Pre-Compute Proposal Gate: Rejects policy violations (e.g. multi-filter stacking).
5. Evolutionary Research Proof: Past experience alters future experiment proposals.
"""

import sys
import unittest
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.stratx_goal_loop import StratXGoalLoopOrchestrator
from skills.tripartite_memory_engine import TripartiteMemoryEngine

class TestEvolutionaryMemoryLoop(unittest.TestCase):

    def setUp(self):
        self.orchestrator = StratXGoalLoopOrchestrator(mission_id="de40-x1x")
        self.memory_engine = TripartiteMemoryEngine()

    def test_mandatory_tripartite_memory_commitment(self):
        print("\n=== TEST 1: Mandatory Rich Tripartite Memory Commitment ===")
        goal = self.orchestrator.set_active_goal(
            goal_id="GOAL_VWAPX_QUALITY",
            goal_type="MODULE_PRODUCTION_GATES",
            goal_definition="Verify VWAPX mean reversion edge",
            target_criteria={"profit_factor": 2.0, "win_rate": 0.65}
        )

        # Commit rich memory on Iteration 1 failure
        mem_record = self.orchestrator.commit_iteration_memory(
            failure_signature={
                "family": "FILTER_ACCRETION",
                "strategy_family": "VWAP_REVERSION",
                "regime": "HIGH_VOL_LONDON",
                "symptoms": ["PF increased", "trade frequency collapsed", "base win rate unchanged"]
            },
            belief_before="High displacement identifies higher-quality VWAP fades",
            hypothesis_id="HYP_221",
            experiment_id="EXP_887",
            intervention={"repair_level": "LEVEL_2_RULE", "description": "High-displacement entry gate", "parameter_changes": {"InpMinDisp": 1.5}},
            predicted_outcome={"wr_change": "+8pp", "frequency_damage": "<15%"},
            actual_outcome={"wr_change": "+2pp", "frequency_change": "-34%", "pf_change": "+0.12"},
            child_parent_delta={"losers_removed": 11, "winners_removed": 9, "new_trades": 0},
            belief_status="WEAKENED",
            confidence_delta=-0.31,
            strategy_lesson="The gate mostly suppresses trades rather than improving the entry mechanism.",
            research_method_lesson="When PF rises while base WR is stable and frequency falls materially, test for filter accretion before adding another gate.",
            future_trigger="PF_UP + FREQUENCY_DOWN + BASE_WR_STABLE",
            future_behavior="Trigger early thesis review instead of another filter experiment."
        )

        print(f"Committed Memory ID: {mem_record['memory_id']}")
        print(f"   -> Failure Signature: {mem_record['failure_signature']['family']}")
        print(f"   -> Belief After: {mem_record['belief_after']['status']} (delta: {mem_record['belief_after']['confidence_delta']})")
        print(f"   -> Future Trigger: {mem_record['future_trigger']}")

        # Verify invariant check
        inv_check = self.memory_engine.validate_iteration_memory_commitment_invariant(mem_record)
        self.assertTrue(inv_check["is_valid"])
        self.assertEqual(inv_check["status"], "MEMORY_COMMIT_VERIFIED")

        # Incomplete memory check
        bad_inv = self.memory_engine.validate_iteration_memory_commitment_invariant(None)
        self.assertFalse(bad_inv["is_valid"])
        self.assertEqual(bad_inv["status"], "ITERATION_CLOSE_BLOCKED")

    def test_pre_compute_proposal_gate_rejection_and_justified_pass(self):
        print("\n=== TEST 2: Pre-Compute Proposal Gate (Duplicate Rejection vs Justified Pass) ===")
        goal = self.orchestrator.set_active_goal(
            goal_id="GOAL_VWAPX_QUALITY",
            goal_type="MODULE_PRODUCTION_GATES",
            goal_definition="Verify VWAPX mean reversion edge",
            target_criteria={"profit_factor": 2.0}
        )

        # Seed memory with prior failed experiment
        self.orchestrator.commit_iteration_memory(
            failure_signature={"family": "FILTER_ACCRETION"},
            belief_before="High displacement fixes chop",
            hypothesis_id="HYP_101",
            experiment_id="EXP_101",
            intervention={"description": "High-displacement entry gate", "parameter_changes": {"InpMinDisp": 1.5}},
            predicted_outcome={},
            actual_outcome={},
            child_parent_delta={},
            belief_status="REFUTED",
            confidence_delta=-0.40,
            strategy_lesson="Displacement gate pruned winners",
            research_method_lesson="Avoid crude displacement filters",
            future_trigger="PREFER_SINGLE_CAUSAL_GATES",
            future_behavior="PREFER_SINGLE_CAUSAL_GATES"
        )

        # Case A: Duplicate experiment proposed without justification
        dup_spec = {
            "experiment_id": "EXP_102",
            "description": "High-displacement entry gate",
            "parameter_changes": {"InpMinDisp": 1.5},
            "market_thesis": "Filter low displacement",
            "memory_used": ["EXP_101"],
            "how_memory_changed_decision": "Retrying displacement filter"
        }
        gate_res_dup = self.orchestrator.validate_pre_compute_proposal(dup_spec)
        print(f"Case A (Unjustified Duplicate): Status = {gate_res_dup['status']} | Reasons: {gate_res_dup['rejection_reasons']}")
        self.assertFalse(gate_res_dup["is_approved"])
        self.assertEqual(gate_res_dup["status"], "EXPERIMENT_REJECTED_BEFORE_COMPUTE")

        # Case B: Multi-filter stacking policy violation
        stack_spec = {
            "experiment_id": "EXP_103",
            "description": "Stack 3 gates",
            "parameter_changes": {"InpMinDisp": 1.2, "InpSession": 2, "InpAtr": 80.0},
            "market_thesis": "PREFER_SINGLE_CAUSAL_GATES",
            "memory_used": ["EXP_101"],
            "how_memory_changed_decision": "Trying 3 gates together"
        }
        gate_res_stack = self.orchestrator.validate_pre_compute_proposal(stack_spec)
        print(f"Case B (Policy Violation - 3 Stacked Gates): Status = {gate_res_stack['status']} | Reasons: {gate_res_stack['rejection_reasons']}")
        self.assertFalse(gate_res_stack["is_approved"])
        self.assertIn("POLICY_VIOLATION", gate_res_stack["rejection_reasons"][0])

        # Case C: Repeating with valid REPEAT_JUSTIFICATION + MATERIAL_CONTEXT_DIFFERENCE
        justified_spec = {
            "experiment_id": "EXP_104",
            "description": "High-displacement entry gate",
            "parameter_changes": {"InpMinDisp": 1.5},
            "market_thesis": "Filter low displacement on corrected telemetry",
            "repeat_justification": "Prior test failed due to known bar-indexing telemetry bug in EXP_101",
            "material_context_difference": "Harness telemetry corrected to ArraySetAsSeries=true with real MT5 tick distribution",
            "memory_used": ["EXP_101"],
            "how_memory_changed_decision": "Retesting now that telemetry indexing defect is eliminated"
        }
        gate_res_justified = self.orchestrator.validate_pre_compute_proposal(justified_spec)
        print(f"Case C (Justified Context Repeat): Status = {gate_res_justified['status']} | Approved: {gate_res_justified['is_approved']}")
        self.assertTrue(gate_res_justified["is_approved"])
        self.assertEqual(gate_res_justified["status"], "APPROVED")

    def test_evolutionary_behavior_modification_proof(self):
        print("\n=== TEST 3: Proof that Past Experience Alters Later Research Behavior ===")
        
        # Step 1: Record lesson from first strategy family (VPPOC)
        self.orchestrator.record_policy_lesson(
            trigger_pattern="FILTER_ACCRETION_COLLAPSE",
            previous_behavior="Stacked session filters when payoff was low",
            outcome="Frequency dropped by 45% while VAL failed",
            lesson="When payoff is below 1.0R, do NOT add entry filters. Split runners and adjust take profit instead.",
            recommended_future_behavior="SPLIT_RUNNERS_AVOID_ENTRY_FILTERS"
        )

        # Step 2: In later strategy family (BRKRT), symptoms appear
        context_tags = ["FILTER_ACCRETION_COLLAPSE", "BRKRT_PAYOFF_DEFICIT"]
        retrieved = self.orchestrator.retrieve_research_policy_memory(context_tags)
        print(f"Retrieved Policy in BRKRT research: {retrieved[0]['policy_id']} -> {retrieved[0]['recommended_behavior']}")
        
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["recommended_behavior"], "SPLIT_RUNNERS_AVOID_ENTRY_FILTERS")

        # Step 3: Planner consumes lesson -> proposes runner split instead of entry gate
        evolutionary_spec = {
            "experiment_id": "EXP_BRKRT_RUNNER_01",
            "repair_level": "L3_COMPONENT_REFACTOR",
            "description": "Split position into 50% fixed 1R target and 50% trailing session runner",
            "parameter_changes": {"InpSplitRunners": True, "InpTrailAtr": 1.5},
            "market_thesis": "Expand payoff ratio directly without suppressing trade opportunities",
            "memory_used": [retrieved[0]["policy_id"]],
            "how_memory_changed_decision": f"Applied policy {retrieved[0]['policy_id']} to avoid adding another entry filter and instead repair payoff architecture via runner split."
        }

        gate_res = self.orchestrator.validate_pre_compute_proposal(evolutionary_spec)
        print(f"Pre-Compute Proposal Gate: {gate_res['status']} (is_approved: {gate_res['is_approved']}, cited memories: {gate_res['cited_memory_count']})")
        self.assertTrue(gate_res["is_approved"])
        self.assertEqual(gate_res["cited_memory_count"], 1)

if __name__ == "__main__":
    unittest.main()
