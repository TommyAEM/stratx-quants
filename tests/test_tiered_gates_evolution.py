"""
StratX Tiered Research Gates Evolution Test (test_tiered_gates_evolution.py)
Validates:
1. Phase 1 Discovery: Allows high trade frequency (50+ trades) and loose RR/WR to collect trade populations.
2. Phase 2 Repair: Sharpens edge and tightens gates (35+ trades, WR>=60%, PF>=1.50, RR>=0.70).
3. Phase 3 Canonical X1X: Strict acceptance (20+ trades, WR>=70%, PF>=2.00, RR>=1.00).
4. Automatic phase graduation and escalation reset across phases.
"""

import sys
import unittest
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.stratx_goal_loop import StratXGoalLoopOrchestrator, RESEARCH_PHASE_GATES

class TestTieredGatesEvolution(unittest.TestCase):

    def setUp(self):
        self.chk_dir = Path("C:/Trading/DE40-Research/checkpoints/test_tiered_chk")
        self.chk_dir.mkdir(parents=True, exist_ok=True)
        self.orchestrator = StratXGoalLoopOrchestrator(
            mission_id="de40-x1x",
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

    def test_full_three_phase_evolutionary_graduation(self):
        print("\n=== TEST: Full 3-Phase Evolutionary Graduation ===")

        goal = self.orchestrator.set_active_goal(
            goal_id="GOAL_TIERED_EVOLUTION",
            goal_type="MODULE_PRODUCTION_GATES",
            goal_definition="Graduate strategy from Phase 1 to Phase 3 X1X",
            initial_phase="PHASE_1_DISCOVERY"
        )

        def mock_progressive_backtest(it: int, phase: str, level: str):
            if phase == "PHASE_1_DISCOVERY":
                # Iteration 1: Passes Phase 1 (55 trades, 52% WR, 1.18 PF, RR=0.50)
                return {
                    "total_trades": 55,
                    "win_rate": 0.52,
                    "profit_factor": 1.18,
                    "risk_reward": 0.50,
                    "max_drawdown": 0.22,
                    "val_retention": 0.60
                }
            elif phase == "PHASE_2_REPAIR":
                if it == 2:
                    # Iteration 2: Fails Phase 2 (PF=1.35 < 1.50)
                    return {
                        "total_trades": 42,
                        "win_rate": 0.58,
                        "profit_factor": 1.35,
                        "risk_reward": 0.65,
                        "max_drawdown": 0.20,
                        "val_retention": 0.68
                    }
                else:
                    # Iteration 3: Passes Phase 2 (38 trades, 63% WR, 1.62 PF, RR=0.78)
                    return {
                        "total_trades": 38,
                        "win_rate": 0.63,
                        "profit_factor": 1.62,
                        "risk_reward": 0.78,
                        "max_drawdown": 0.18,
                        "val_retention": 0.72
                    }
            else: # PHASE_3_CANONICAL_X1X
                if it == 4:
                    # Iteration 4: Fails Phase 3 (WR=68% < 70%, PF=1.85 < 2.00)
                    return {
                        "total_trades": 26,
                        "win_rate": 0.68,
                        "profit_factor": 1.85,
                        "risk_reward": 0.95,
                        "max_drawdown": 0.15,
                        "val_retention": 0.80
                    }
                else:
                    # Iteration 5: Passes strict Canonical X1X!
                    return {
                        "total_trades": 24,
                        "win_rate": 0.72,
                        "profit_factor": 2.25,
                        "risk_reward": 1.08,
                        "max_drawdown": 0.14,
                        "val_retention": 0.86
                    }

        final_state = self.orchestrator.run_goal_mission_loop(
            goal_dict=goal,
            mock_backtest_fn=mock_progressive_backtest,
            max_test_iterations=10
        )

        # 1. Check final goal status
        self.assertEqual(final_state["goal_status"], "PASSED")
        self.assertEqual(final_state["research_phase"], "PHASE_3_CANONICAL_X1X")
        self.assertEqual(final_state["iteration"], 5)
        print("\nAssertion Passed: Successfully graduated through all 3 phases and reached PASSED on Iteration 5.")

        # 2. Check history records reflect phase transitions
        phases_in_history = [h["research_phase"] for h in final_state["history"]]
        self.assertEqual(phases_in_history[0], "PHASE_1_DISCOVERY")
        self.assertEqual(phases_in_history[1], "PHASE_2_REPAIR")
        self.assertEqual(phases_in_history[2], "PHASE_2_REPAIR")
        self.assertEqual(phases_in_history[3], "PHASE_3_CANONICAL_X1X")
        self.assertEqual(phases_in_history[4], "PHASE_3_CANONICAL_X1X")
        print("Assertion Passed: History accurately captures phase lineage: Phase 1 -> Phase 2 -> Phase 3.")

        # 3. Check state on disk
        state_file = self.chk_dir / f"STATE_{goal['goal_id']}.json"
        self.assertTrue(state_file.exists())
        loaded = json.loads(state_file.read_text())
        self.assertEqual(loaded["research_phase"], "PHASE_3_CANONICAL_X1X")
        self.assertEqual(loaded["goal_status"], "PASSED")
        print("Assertion Passed: State file persisted on disk matches final graduation.")

if __name__ == "__main__":
    unittest.main()
