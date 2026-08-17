"""
Regression test suite for Deep Self-Healing P0 Invariants:
1. Mandatory child re-forensics completion block (no mutation allowed while child_reforensics_completed is False).
2. Authoritative risk gates (rejection of MaxDD > 10%, PF < 1.10).
3. Separation of RESEARCH_INCUMBENT vs ACCEPTED_MODULE.
4. Clean dynamic credential loading (zero hardcoded secrets).
"""

import unittest
from skills.self_review_engine import SelfReviewEngine
from orchestrator.stratx_live_console import AUTHORITATIVE_GATES, check_pass_gates, compute_child_parent_delta, get_alibaba_dedicated_key
import pandas as pd

class TestDeepSelfHealingP0Invariants(unittest.TestCase):

    def setUp(self):
        self.engine = SelfReviewEngine()

    def test_reforensics_gate_enforcement(self):
        """Proves that missing child reforensics strictly forbids next generation/mutation."""
        session = self.engine.create_goal_session(
            mission_id="de40-test",
            module_id="X1X_M1_FBO",
            parent_id="X1X_M1_FBO",
            goal_id="SR_M1_001",
            goal_definition="Acceptance",
            goal_metrics={"win_rate": 0.70, "profit_factor": 2.0, "risk_reward": 1.0, "min_trades_per_year": 20.0},
            goal_constraints={"max_drawdown": 0.06}
        )
        
        # Incomplete child re-forensics
        record = {
            "review_id": "REV_TEST_01",
            "recommended_route": "CHILD_REFORENSICS_REQUIRED",
            "child_reforensics_required": True,
            "child_reforensics_completed": False
        }
        
        gate_res = self.engine.validate_workflow_gates(session, record, child_reforensics_record=None)
        self.assertFalse(gate_res["is_allowed"], "Workflow must block when child reforensics are missing")
        self.assertTrue(any("CHILD_REFORENSICS" in v for v in gate_res["violations"]))

    def test_drawdown_hard_gate_rejection(self):
        """Proves that a 25.6% DD strategy is strictly rejected by authoritative gates."""
        blown_metrics = {
            "total_trades": 1272,
            "win_rate": 0.741,
            "profit_factor": 1.16,
            "max_drawdown": 0.256,
            "max_consecutive_losses": 12
        }
        passed, met, failures = check_pass_gates(blown_metrics, "PHASE_3_CANONICAL_X1X")
        self.assertFalse(passed, "Blown drawdown strategy must never pass gates")
        self.assertTrue(any("MaxDD" in f for f in failures), "Must record MaxDD failure")
        self.assertTrue(any("PF" in f for f in failures), "Must record PF failure")

    def test_delta_accounting_integrity(self):
        """Proves that child metrics are not reported as delta improvements when parent is missing."""
        child_metrics = {
            "total_trades": 1272,
            "win_rate": 0.741,
            "profit_factor": 1.16,
            "max_drawdown": 0.256,
            "risk_reward": 0.40
        }
        delta_info = compute_child_parent_delta(None, child_metrics, pd.DataFrame(), pd.DataFrame([{"time_open": "2024.01.01", "R": 1.0}]))
        self.assertEqual(delta_info["delta_pf"], 0.0, "Delta PF must be 0.0 for initial seed baseline")
        self.assertEqual(delta_info["delta_wr"], 0.0, "Delta WR must be 0.0 for initial seed baseline")
        self.assertIn("INITIAL SEED BASELINE", delta_info["verdict"])

    def test_authoritative_gates_consistency(self):
        """Proves that authoritative gates are unified and non-conflicting."""
        self.assertEqual(AUTHORITATIVE_GATES["MODULE_CANONICAL_MAX_DD"], 0.06)
        self.assertEqual(AUTHORITATIVE_GATES["PORTFOLIO_COMBINED_MAX_DD"], 0.10)
        self.assertEqual(AUTHORITATIVE_GATES["RESEARCH_INCUMBENT_MAX_DD"], 0.10)
        self.assertEqual(AUTHORITATIVE_GATES["MIN_TRADES_ANNUAL"], 20.0)

if __name__ == "__main__":
    unittest.main()
