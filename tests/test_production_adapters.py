"""
StratX Production Integration Edge Case Tests (test_production_adapters.py)
Validates:
1. Strict JSON extraction from markdown / conversational text.
2. Fast compiler loop log parsing and error classification.
3. Top-K Memory Retriever scoring and token budget capping (< 4000 tokens).
4. Atomic state persistence & crash auto-recovery.
"""

import sys
import unittest
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.llm_client import StratXLLMClient
from orchestrator.compiler_loop import MQL5CompilerLoop
from orchestrator.memory_retriever import MemoryRetriever
from orchestrator.state_persistence import StatePersistenceManager

class TestProductionAdapters(unittest.TestCase):

    def setUp(self):
        self.llm_client = StratXLLMClient()
        self.compiler = MQL5CompilerLoop()
        self.retriever = MemoryRetriever()
        self.persistence = StatePersistenceManager(checkpoint_dir=Path("C:/Trading/DE40-Research/checkpoints/test_chk"))

    def tearDown(self):
        # Clean up test checkpoints
        test_dir = Path("C:/Trading/DE40-Research/checkpoints/test_chk")
        if test_dir.exists():
            for f in test_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                test_dir.rmdir()
            except Exception:
                pass

    def test_json_extractor_resilience(self):
        print("\n=== TEST 1: Strict JSON Extractor Resilience ===")
        # Case A: Wrapped in ```json ... ``` with conversational preamble
        messy_response = """
        Sure! Here is the completed experiment specification you requested:
        ```json
        {
            "experiment_id": "EXP_001",
            "market_thesis": "Filter low volatility Asian chop",
            "parameter_changes": {"InpMinDisp": 1.2}
        }
        ```
        Let me know if you need anything else!
        """
        parsed = self.llm_client.extract_json(messy_response)
        self.assertEqual(parsed["experiment_id"], "EXP_001")
        self.assertEqual(parsed["parameter_changes"]["InpMinDisp"], 1.2)
        print("Case A (Markdown wrapped with preamble): Successfully extracted JSON.")

        # Case B: Plain JSON without code blocks
        plain_json = '{"review_id": "REV_100", "prediction_match": "CONFIRMED"}'
        parsed_b = self.llm_client.extract_json(plain_json)
        self.assertEqual(parsed_b["review_id"], "REV_100")
        print("Case B (Plain JSON): Successfully extracted JSON.")

    def test_compiler_log_parsing(self):
        print("\n=== TEST 2: Compiler Log Parsing ===")
        # Simulate clean log
        log_clean = Path("C:/Trading/DE40-Research/checkpoints/test_chk/clean.log")
        log_clean.parent.mkdir(parents=True, exist_ok=True)
        log_clean.write_text("0 error(s), 0 warning(s), 23 msec elapsed", encoding="utf-8")
        
        res_clean = self.compiler.parse_compile_log(log_clean)
        self.assertTrue(res_clean["success"])
        self.assertEqual(res_clean["error_count"], 0)
        print("Clean compile log: 0 errors, 0 warnings -> SUCCESS")

        # Simulate error log
        log_err = Path("C:/Trading/DE40-Research/checkpoints/test_chk/error.log")
        log_err.write_text("DE40_Strategy.mq5(45,12) : error 256: ';' - semicolon expected\n1 error(s), 0 warning(s)", encoding="utf-8")
        res_err = self.compiler.parse_compile_log(log_err)
        self.assertFalse(res_err["success"])
        self.assertEqual(res_err["error_count"], 1)
        self.assertIn("semicolon expected", res_err["errors"][0])
        print("Error compile log: Correctly caught syntax error.")

    def test_memory_retriever_budget_capping(self):
        print("\n=== TEST 3: Top-K Memory Retrieval & Budget Capping ===")
        memories = [
            {
                "memory_id": f"MEM_{i}",
                "failure_signature": {"family": "FILTER_ACCRETION" if i % 2 == 0 else "STOP_CHOP", "symptoms": ["PF increased", "volume dropped"]},
                "future_trigger": "PF_UP + FREQUENCY_DOWN",
                "strategy_lesson": "Sample strategy lesson description" * 5,
                "research_method_lesson": "Sample method lesson" * 5,
                "confidence": 0.90
            }
            for i in range(20)
        ]

        top_k = self.retriever.retrieve_top_k(memories, query_tags=["FILTER_ACCRETION"], top_k=4)
        self.assertEqual(len(top_k), 4)
        self.assertEqual(top_k[0]["failure_signature"]["family"], "FILTER_ACCRETION")
        
        # Verify strict character budget capping
        total_len = len(json.dumps(top_k))
        self.assertLess(total_len, MemoryRetriever.MAX_MEMORY_CHARS)
        print(f"Retrieved Top-4 Memories (Size: {total_len} chars < {MemoryRetriever.MAX_MEMORY_CHARS} limit) -> PASSED")

    def test_state_persistence_and_crash_recovery(self):
        print("\n=== TEST 4: Atomic State Persistence & Crash Auto-Recovery ===")
        session = {
            "goal_id": "GOAL_M1_TEST",
            "mission_id": "de40-x1x",
            "goal_status": "ACTIVE",
            "iteration": 4,
            "current_candidate_id": "CANDIDATE_IT4",
            "history": [{"iteration": 1}, {"iteration": 2}, {"iteration": 3}]
        }

        # Save state atomically
        saved_path = self.persistence.save_goal_state(session)
        self.assertTrue(saved_path.exists())
        print(f"Atomically saved goal state: {saved_path.name}")

        # Simulate system reboot & crash recovery
        recovered_session = self.persistence.find_active_goal_session()
        self.assertIsNotNone(recovered_session)
        self.assertEqual(recovered_session["goal_id"], "GOAL_M1_TEST")
        self.assertEqual(recovered_session["iteration"], 4)
        self.assertEqual(len(recovered_session["history"]), 3)
        print(f"Crash Recovery: Successfully recovered active session {recovered_session['goal_id']} at Iteration {recovered_session['iteration']}.")

if __name__ == "__main__":
    unittest.main()
