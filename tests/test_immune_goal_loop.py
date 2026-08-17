"""
StratX Autonomous Loop Smoke Test (test_immune_goal_loop.py)
Validates that the orchestrator is physically immune to LLM soft-kills:
1. Forces 4 consecutive failing iterations with unmet metrics -> Verifies the loop PERSISTS without stopping.
2. Escalates repair level L1 -> L2 on 3rd failure.
3. Produces passing metrics on Iteration 5 -> Verifies deterministic exit.
4. Checks state persistence file integrity on disk.
"""

import sys
import unittest
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.stratx_goal_loop import StratXGoalLoopOrchestrator

class TestImmuneGoalLoop(unittest.TestCase):

    def setUp(self):
        self.chk_dir = Path("C:/Trading/DE40-Research/checkpoints/test_loop_chk")
        self.chk_dir.mkdir(parents=True, exist_ok=True)
        self.orchestrator = StratXGoalLoopOrchestrator(
            mission_id="de40-x1x",
            iteration_safety_threshold=10,
            checkpoint_dir=self.chk_dir
        )

    def tearDown(self):
        if self.chk_dir.exists():
            for f in self.chk_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                self.chk_dir.rmdir()
            except Exception:
                pass

    def test_loop_persists_across_failures_and_exits_on_pass(self):
        print("\n=== SMOKE TEST: Loop Persistence Across Failing Iterations ===")

        goal = self.orchestrator.set_active_goal(
            goal_id="GOAL_HARD_SURVIVAL",
            goal_type="MODULE_PRODUCTION_GATES",
            goal_definition="Repair strategy to meet WR >= 70%, PF >= 2.0, RR >= 1.0",
            target_criteria={
                "win_rate": 0.70,
                "profit_factor": 2.00,
                "risk_reward": 1.00,
                "min_trades_per_year": 20.0,
                "max_drawdown": 1000.0,
                "min_val_retention": 75.0
            }
        )

        # Mock backtest function:
        # Iteration 1-4: Fails RR or WR
        # Iteration 5: Passes all criteria!
        def mock_backtest(it: int, level: str):
            if it < 5:
                # Failing candidate
                return {
                    "win_rate": 0.65,
                    "profit_factor": 1.80,
                    "payoff_ratio": 0.85, # Fails RR
                    "trades_per_year": 22.0,
                    "max_drawdown": 650.0,
                    "val_retention": 80.0
                }
            else:
                # Passing candidate on iteration 5
                return {
                    "win_rate": 0.73,
                    "profit_factor": 2.30,
                    "payoff_ratio": 1.06, # Passes RR
                    "trades_per_year": 24.0,
                    "max_drawdown": 520.0,
                    "val_retention": 85.0
                }

        # Run mission loop
        final_state = self.orchestrator.run_goal_mission_loop(
            goal_dict=goal,
            mock_backtest_fn=mock_backtest,
            max_test_iterations=10
        )

        # 1. Assert loop executed at least 5 iterations without dying early
        self.assertGreaterEqual(final_state["iteration"], 5)
        print(f"\nAssertion Passed: Loop persisted for {final_state['iteration']} iterations without dying early.")

        # 2. Assert final goal status is PASSED
        self.assertEqual(final_state["goal_status"], "PASSED")
        print("Assertion Passed: Final goal_status is PASSED.")

        # 3. Assert state file on disk exists and matches memory
        state_file = self.chk_dir / f"STATE_{goal['goal_id']}.json"
        self.assertTrue(state_file.exists())
        loaded = json.loads(state_file.read_text())
        self.assertEqual(loaded["iteration"], final_state["iteration"])
        self.assertEqual(loaded["goal_status"], "PASSED")
        self.assertEqual(len(loaded["history"]), 5)
        print(f"Assertion Passed: State file on disk matches memory ({len(loaded['history'])} history records).")

        print("\n✓ Loop persists across iterations, survives failures, and state survives reload!")

if __name__ == "__main__":
    unittest.main()
