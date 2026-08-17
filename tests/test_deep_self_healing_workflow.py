"""
StratX Deep Self-Healing Workflow Regression Suite (test_deep_self_healing_workflow.py)
Implements the mandatory regression tests A-J from the forensic audit mission.

Run with the project Python environment (requires scipy/pandas/numpy):
    python -m unittest tests.test_deep_self_healing_workflow -v
"""

import sys
import json
import math
import types
import tempfile
import unittest
from pathlib import Path

# --- Degraded-environment guard: stub scipy only when truly absent -------------
try:
    import scipy  # noqa: F401
except ImportError:
    scipy_stub = types.ModuleType("scipy")
    stats_stub = types.ModuleType("scipy.stats")

    class _Norm:
        @staticmethod
        def cdf(z):
            return 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0)))

    class _T:
        @staticmethod
        def cdf(t, df):
            return 0.5 * (1.0 + math.erf(float(t) / math.sqrt(2.0)))

    class _Binom:
        @staticmethod
        def cdf(k, n, p):
            return 0.5

    stats_stub.norm = _Norm()
    stats_stub.t = _T()
    stats_stub.binom = _Binom()
    stats_stub.skew = lambda x: 0.0
    stats_stub.kurtosis = lambda x, fisher=False: 3.0
    stats_stub.linregress = lambda x, y: (0.0, 0.0, 0.0, 1.0, 0.0)
    scipy_stub.stats = stats_stub
    sys.modules["scipy"] = scipy_stub
    sys.modules["scipy.stats"] = stats_stub

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from orchestrator.stratx_live_console import (
    compute_child_parent_delta,
    compute_matched_winner_analysis,
    compute_population_enrichment,
    compute_real_yearly_metrics,
    count_mutation_diff,
    apply_params_to_code,
    enforce_memory_commitment,
    evaluate_final_portfolio_gates,
    format_population_enrichment_block,
    is_dead_population,
    pre_compute_debunked_gate,
    run_governor_decision,
    run_independent_review,
    safe_parse_json,
    check_pass_gates,
    MODULE_MIN_TRADES_PER_YEAR,
    CHAMPION_MIN_TRADES,
    FORCED_FREQUENCY_RESTORATION,
)
import orchestrator.stratx_live_console as console_mod
from orchestrator.stratx_goal_loop import StratXGoalLoopOrchestrator
from skills.self_review_engine import SelfReviewEngine


def _df(n, start_day=1, rs=None):
    rs = rs if rs is not None else ([1.0, -1.0] * (n // 2 + 1))[:n]
    return pd.DataFrame({
        "time_open": [f"2023.09.{(start_day + i) % 28 + 1:02d} 10:00:00" for i in range(n)],
        "R": rs
    })


class TestDeepSelfHealingWorkflow(unittest.TestCase):

    # --------------------------------------------------------------- TEST A
    def test_A_goal_unmet_same_goal_next_iteration(self):
        """Todos complete but goal fails RR -> SAME self_review_goal_id, exit forbidden."""
        eng = SelfReviewEngine()
        goal = eng.create_goal_session(
            mission_id="de40-x1x", module_id="M1", parent_id="P",
            goal_id="SR_M1_001", goal_definition="M1 acceptance",
            goal_metrics={"win_rate": 0.70, "profit_factor": 2.0, "risk_reward": 1.0,
                          "min_trades_per_year": 20.0},
            goal_constraints={}
        )
        # Excellent WR/PF must NOT hide the RR failure (no metric cherry-picking)
        res = eng.evaluate_goal(goal, "C1",
                                {"win_rate": 0.75, "profit_factor": 3.2, "risk_reward": 0.82,
                                 "trades_per_year": 24.0},
                                {"net_R_delta": 1.0, "frequency_retention_pct": 95.0})
        self.assertFalse(res["all_passed"])
        self.assertEqual(goal["goal_id"], "SR_M1_001")
        exit_check = eng.can_exit_self_review(goal)
        self.assertFalse(exit_check["can_exit"])
        self.assertEqual(exit_check["reason"], "SELF_REVIEW_GOAL_UNMET")
        self.assertEqual(exit_check["allowed_next_stage"], "SELF_REVIEW_ITERATION")
        eng.advance_iteration(goal)
        self.assertEqual(goal["iteration"], 2)
        self.assertEqual(goal["goal_id"], "SR_M1_001")

        # Frequency failure variant: WR 72 / PF 2.4 / RR 1.05 / Freq 12 -> UNMET
        ok, met, fail = check_pass_gates(
            {"total_trades": 12, "win_rate": 0.72, "profit_factor": 2.4, "risk_reward": 1.05,
             "max_drawdown": 0.05, "max_consecutive_losses": 3},
            "PHASE_3_CANONICAL_X1X")
        self.assertFalse(ok)
        self.assertTrue(any("Frequency" in f for f in fail))

    # --------------------------------------------------------------- TEST B
    def test_B_child_n1_sample_insufficient(self):
        """Child N=1 -> SAMPLE_INSUFFICIENT + FREQUENCY_COLLAPSE, no single-trade causal claim."""
        parent = _df(10)
        child = _df(1, rs=[1.0])
        d = compute_child_parent_delta(
            {"total_trades": 10, "win_rate": 0.6, "profit_factor": 1.8},
            {"total_trades": 1, "win_rate": 1.0, "profit_factor": 99.0},
            parent, child)
        self.assertTrue(d["is_sample_insufficient"])
        self.assertTrue(d["is_freq_collapse"])
        self.assertIn("NOT statistically interpretable", d["verdict"])
        # Primary question must be about WHY the mutation destroyed the population,
        # never a causal diagnosis of the single child trade.
        self.assertIn("eliminate", d["primary_question"].lower())

    # --------------------------------------------------------------- TEST C
    def test_C_population_destruction_collapse_analysis(self):
        """Child removes >=80% of parent trades -> collapse analysis, not loss storytelling."""
        parent = _df(100)
        child = _df(5)
        d = compute_child_parent_delta(
            {"total_trades": 100, "win_rate": 0.61, "profit_factor": 1.5},
            {"total_trades": 5, "win_rate": 0.80, "profit_factor": 3.4},
            parent, child)
        self.assertTrue(d["is_freq_collapse"])
        self.assertIn("COLLAPSE", d["verdict"].upper())
        self.assertIn("gate", d["primary_question"].lower())
        self.assertAlmostEqual(d["pct_trade_change"], -95.0, places=1)

    # --------------------------------------------------------------- TEST D
    def test_D_reviewer_rejection_reopens_same_goal(self):
        """Self-review passes but Independent Reviewer rejects -> SAME goal reopened."""
        eng = SelfReviewEngine()
        goal = eng.create_goal_session(
            mission_id="de40-x1x", module_id="M1", parent_id="P",
            goal_id="SR_M1_001", goal_definition="M1 acceptance",
            goal_metrics={"win_rate": 0.70, "profit_factor": 2.0, "risk_reward": 1.0,
                          "min_trades_per_year": 20.0},
            goal_constraints={}
        )
        res = eng.evaluate_goal(goal, "C_OK",
                                {"win_rate": 0.72, "profit_factor": 2.2, "risk_reward": 1.03,
                                 "trades_per_year": 22.0},
                                {"net_R_delta": 4.1, "frequency_retention_pct": 90.0})
        self.assertTrue(res["all_passed"])
        self.assertTrue(eng.can_exit_self_review(goal)["can_exit"])

        # Independent reviewer finds the walk-forward evidence is fabricated/missing
        review = run_independent_review(
            module_name="M1", child_metrics={"win_rate": 0.72, "profit_factor": 2.2,
                                             "risk_reward": 1.03, "total_trades": 29},
            annualized_trades=22.0, wf_passed=False, wf_reason="VALIDATION_EVIDENCE_UNAVAILABLE",
            t_quant={"passed": True, "t_stat": 3.0, "p_value": 0.001},
            delta_info={"is_freq_collapse": False, "is_sample_insufficient": False},
            portfolio_modules=[], wf_evidence_available=False)
        self.assertEqual(review["verdict"], "FAIL")
        self.assertEqual(review["loopback"], "REOPEN_SAME_SELF_REVIEW_GOAL")

        # Reopen the SAME goal with objections (console admission-path semantics)
        goal["goal_status"] = "REASSESSING"
        goal["status"] = "REASSESSING"
        goal.setdefault("reviewer_objections", []).extend(review["objections"])
        eng.advance_iteration(goal)
        self.assertEqual(goal["goal_id"], "SR_M1_001")
        self.assertIn("VALIDATION_EVIDENCE_UNAVAILABLE", " ".join(goal["reviewer_objections"]))
        self.assertFalse(eng.can_exit_self_review(goal)["can_exit"])

    # --------------------------------------------------------------- TEST E
    def test_E_governor_return_to_self_review(self):
        """Governor RETURN_TO_SELF_REVIEW -> same goal reopened, not workflow completion."""
        review_fail = {"verdict": "FAIL", "objections": ["T-quant insignificance"]}
        gov = run_governor_decision(review_fail, {})
        self.assertEqual(gov["decision"], "RETURN_TO_SELF_REVIEW")
        self.assertEqual(gov["next"], "REOPEN_SAME_SELF_REVIEW_GOAL_WITH_OBJECTIONS")

        review_pass = {"verdict": "PASS", "objections": []}
        gov2 = run_governor_decision(review_pass, {})
        self.assertEqual(gov2["decision"], "PROMOTE")
        self.assertEqual(gov2["next"], "FREEZE_MODULE_AND_OPEN_NEXT_PORTFOLIO_GOAL")

    # --------------------------------------------------------------- TEST F
    def test_F_memory_commit_invariant_blocks_next_iteration(self):
        """Iteration ends without memory commit -> next iteration blocked until tombstone committed."""
        with tempfile.TemporaryDirectory() as td:
            tmp_brain = Path(td) / "brain.json"
            orig = console_mod.BRAIN_FILE
            console_mod.BRAIN_FILE = tmp_brain
            try:
                state = {"awaiting_memory_commit": True, "iteration": 7}
                violated = enforce_memory_commitment(state, "M1_TEST")
                self.assertTrue(violated)
                self.assertFalse(state["awaiting_memory_commit"])
                brain = json.loads(tmp_brain.read_text(encoding="utf-8"))
                self.assertEqual(brain[-1]["fix"], "INTERRUPTED_ITERATION_TOMBSTONE")
                # Clean state: no block
                self.assertFalse(enforce_memory_commitment(state, "M1_TEST"))
            finally:
                console_mod.BRAIN_FILE = orig

    # --------------------------------------------------------------- TEST G
    def test_G_memory_retrieved_before_experiment_and_debunked_gate(self):
        """Relevant Policy Memory must be retrieved before experiment selection;
        pre-compute gate rejects debunked repeats without justification."""
        orch = StratXGoalLoopOrchestrator(mission_id="de40-x1x",
                                          checkpoint_dir=Path(tempfile.mkdtemp()))
        orch.record_policy_lesson(
            trigger_pattern="FILTER_ACCRETION",
            previous_behavior="stacked filters",
            outcome="frequency collapse",
            lesson="Filter accretion destroys trade population",
            recommended_future_behavior="Prefer single causal gates"
        )
        matches = orch.retrieve_research_policy_memory(["FILTER_ACCRETION"])
        self.assertTrue(matches, "Policy memory must be retrieved before experiment selection")
        self.assertIn("policy_id", matches[0])

        with tempfile.TemporaryDirectory() as td:
            tmp_brain = Path(td) / "brain.json"
            tmp_brain.write_text(json.dumps([
                {"fix": "add volatility gate", "status": "DEBUNKED", "confidence": 0.15, "times_attempted": 2}
            ]), encoding="utf-8")
            orig = console_mod.BRAIN_FILE
            console_mod.BRAIN_FILE = tmp_brain
            try:
                gate = pre_compute_debunked_gate("add volatility gate")
                self.assertFalse(gate["is_approved"])
                self.assertIn("DUPLICATE_LOW_EIV", gate["rejection_reasons"][0])
                gate2 = pre_compute_debunked_gate("completely different structural change")
                self.assertTrue(gate2["is_approved"])
            finally:
                console_mod.BRAIN_FILE = orig

    # --------------------------------------------------------------- TEST H
    def test_H_action_done_does_not_complete_mission(self):
        """One role/action completing while mission is ACTIVE -> automatic continuation."""
        orch = StratXGoalLoopOrchestrator(mission_id="de40-x1x",
                                          checkpoint_dir=Path(tempfile.mkdtemp()))
        goal = orch.set_active_goal(
            goal_id="GOAL_TEST_H", goal_type="MODULE_PRODUCTION_GATES",
            goal_definition="test", initial_phase="PHASE_1_DISCOVERY")

        def failing_backtest(it, phase=None, level=None):
            return {"total_trades": 40, "win_rate": 0.45, "profit_factor": 0.9,
                    "risk_reward": 0.4, "max_drawdown": 0.20, "val_retention": 0.5}

        final = orch.run_goal_mission_loop(goal_dict=goal, mock_backtest_fn=failing_backtest,
                                           max_test_iterations=4)
        # Iterations kept running automatically; the mission never marked itself DONE.
        self.assertGreaterEqual(final["iteration"], 4)
        self.assertIn(final["goal_status"], ["ACTIVE", "ESCALATE"])
        self.assertNotEqual(final["goal_status"], "DONE")

    # --------------------------------------------------------------- TEST I
    def test_I_module_pass_freezes_and_mission_continues(self):
        """M1 passing must freeze M1 and open the next portfolio goal; mission stays ACTIVE."""
        # Reviewer PASS -> Governor PROMOTE -> freeze + next goal
        review = run_independent_review(
            module_name="M1", child_metrics={"win_rate": 0.71, "profit_factor": 2.1,
                                             "risk_reward": 1.05, "total_trades": 30},
            annualized_trades=22.5, wf_passed=True, wf_reason="ok",
            t_quant={"passed": True, "t_stat": 3.1, "p_value": 0.0009},
            delta_info={"is_freq_collapse": False, "is_sample_insufficient": False},
            portfolio_modules=[], wf_evidence_available=True)
        self.assertEqual(review["verdict"], "PASS")
        gov = run_governor_decision(review, {})
        self.assertEqual(gov["decision"], "PROMOTE")
        self.assertEqual(gov["next"], "FREEZE_MODULE_AND_OPEN_NEXT_PORTFOLIO_GOAL")

        # M1 PASS != MISSION PASS: with one admitted module the portfolio gate fails open
        pg = evaluate_final_portfolio_gates(
            [{"name": "M1", "annualized_trades": 22.5}], combined_max_dd=0.04)
        self.assertFalse(pg["passed"])
        self.assertTrue(any("< 5" in f for f in pg["failures"]))

    # --------------------------------------------------------------- TEST J
    def test_J_final_portfolio_dd_gate(self):
        """5 accepted modules but combined DD >= 10% -> FINAL PORTFOLIO FAIL, healing continues."""
        modules = [{"name": f"M{i}", "annualized_trades": 25.0} for i in range(1, 6)]
        pg = evaluate_final_portfolio_gates(modules, combined_max_dd=0.12)
        self.assertFalse(pg["passed"])
        self.assertTrue(any("FINAL_PORTFOLIO_FAIL" in f for f in pg["failures"]))

        pg_ok = evaluate_final_portfolio_gates(modules, combined_max_dd=0.08)
        self.assertTrue(pg_ok["passed"])

        pg_unverified = evaluate_final_portfolio_gates(modules, combined_max_dd=None)
        self.assertFalse(pg_unverified["passed"])
        self.assertTrue(any("COMBINED_DD_UNVERIFIED" in f for f in pg_unverified["failures"]))

    # ------------------------------------------------------- SUPPORTING GUARDS
    def test_neutral_llm_fallbacks_no_fabricated_fix(self):
        """Silent LLM failure must never fabricate a trading decision."""
        r = safe_parse_json("")
        self.assertIsNone(r["recommended_fix"])
        self.assertEqual(r["council_verdict"], "INSUFFICIENT_EVIDENCE")
        r2 = safe_parse_json("garbage {{not json")
        self.assertIsNone(r2.get("recommended_fix"))

    def test_matched_winner_engine_separates_cohorts(self):
        """Matched-winner engine compares losers vs winners of the SAME population."""
        df = _df(12)
        df["gmt_hour"] = [8] * 6 + [14] * 6
        df["R"] = [-1.0] * 5 + [1.0] + [1.0] * 6
        mw = compute_matched_winner_analysis(df)
        self.assertIsNotNone(mw)
        self.assertEqual(mw["loser_count"], 5)
        self.assertEqual(mw["winner_count"], 7)
        self.assertTrue(mw["top_separating_features"])
        # Insufficient population -> no analysis (sample-size discipline)
        self.assertIsNone(compute_matched_winner_analysis(_df(3)))

    def test_real_yearly_metrics_no_fabrication(self):
        """Per-year walk-forward metrics must come from REAL trades or be UNAVAILABLE."""
        df = pd.DataFrame({
            "time_open": ["2023.10.02 10:00:00", "2023.11.03 10:00:00",
                          "2024.01.05 10:00:00", "2024.02.06 10:00:00"],
            "R": [1.0, -1.0, 1.0, 1.0]
        })
        yearly = compute_real_yearly_metrics(df)
        self.assertIsNotNone(yearly)
        self.assertIn("2023", yearly)
        self.assertIn("2024", yearly)
        self.assertEqual(yearly["2024"]["win_rate"], 1.0)
        # No time column -> UNAVAILABLE (fabrication forbidden)
        self.assertIsNone(compute_real_yearly_metrics(pd.DataFrame({"R": [1.0, -1.0]})))

    def test_module_frequency_floor_is_20(self):
        """Authoritative module floor is 20 logical trades/year (not 15)."""
        self.assertEqual(MODULE_MIN_TRADES_PER_YEAR, 20.0)
        review = run_independent_review(
            module_name="M1", child_metrics={"win_rate": 0.75, "profit_factor": 2.5,
                                             "risk_reward": 1.1, "total_trades": 24},
            annualized_trades=18.0, wf_passed=True, wf_reason="ok",
            t_quant={"passed": True, "t_stat": 3.0, "p_value": 0.001},
            delta_info={"is_freq_collapse": False, "is_sample_insufficient": False},
            portfolio_modules=[], wf_evidence_available=True)
        self.assertEqual(review["verdict"], "FAIL")
        self.assertTrue(any("20" in o for o in review["objections"]))

    def test_K_dead_population_never_owns_baseline(self):
        """TEST K (anti-stall): a 1-trade dead result is DEAD and must never be
        promoted as champion nor own the compounding parent baseline."""
        self.assertTrue(is_dead_population({"total_trades": 1, "win_rate": 0.0,
                                            "profit_factor": 0.0, "dead_strategy": True}))
        self.assertTrue(is_dead_population({"total_trades": 4}))
        self.assertTrue(is_dead_population(None))
        self.assertFalse(is_dead_population({"total_trades": CHAMPION_MIN_TRADES}))
        self.assertFalse(is_dead_population({"total_trades": 40, "dead_strategy": False}))

    def test_L_escalation_reachable_from_every_failure_path(self):
        """TEST L (anti-stall): the shared repair-ladder helper escalates after
        MAX_FAILS_PER_LEVEL — including the forensics-only non-mutation path
        that previously stalled the repair level at L0 forever."""
        console = console_mod.StratXLiveConsole.__new__(console_mod.StratXLiveConsole)
        console.REPAIR_LEVELS = ["L1_PARAMETER", "L2_SESSION_TIME", "L3_INDICATOR_LOGIC",
                                 "L4_ARCHITECTURE", "L5_PIVOT_NEW_ALPHA"]
        console.MAX_FAILS_PER_LEVEL = 3
        console.MAX_ITERATIONS_PER_THESIS = 35
        state = {"repair_level_idx": 0, "consecutive_fails_at_level": 3,
                 "thesis_iteration_count": 10}
        console._escalate_repair_ladder(state, "X1X_M1_FBO")
        self.assertEqual(state["repair_level_idx"], 1)
        self.assertEqual(state["consecutive_fails_at_level"], 0)
        # Deep incubation lock: L5 ceiling + budget remaining -> restart at L1, no pivot
        state = {"repair_level_idx": 4, "consecutive_fails_at_level": 3,
                 "thesis_iteration_count": 10}
        console._escalate_repair_ladder(state, "X1X_M1_FBO")
        self.assertEqual(state["repair_level_idx"], 0)
        # Budget exhausted -> lineage discarded, pivot permitted
        state = {"repair_level_idx": 4, "consecutive_fails_at_level": 3,
                 "thesis_iteration_count": 35, "champion_code": "X", "champion_thesis": "T",
                 "champion_metrics": {}, "champion_params": None, "champion_score": 10.0,
                 "lineage_note": "x", "iterations_since_improvement": 2,
                 "temperature": 1.0, "forced_jab": "y"}
        console._escalate_repair_ladder(state, "X1X_M1_FBO")
        self.assertIsNone(state["champion_code"])
        self.assertEqual(state["champion_score"], -1e18)
        self.assertEqual(state["thesis_iteration_count"], 0)

    def test_M_dead_champion_recycle_restores_template_baseline(self):
        """TEST M (baseline recycling): _reset_champion_lineage clears the dead
        lineage so active_thesis['base_code'] reclaims the parent baseline."""
        console = console_mod.StratXLiveConsole.__new__(console_mod.StratXLiveConsole)
        state = {"champion_code": "dead_code", "champion_metrics": {"total_trades": 1},
                 "champion_params": None, "champion_score": -82.0, "lineage_note": "old"}
        console._reset_champion_lineage(state, note="DEAD CHAMPION RECYCLED")
        self.assertIsNone(state["champion_code"])
        self.assertIsNone(state["champion_metrics"])
        self.assertEqual(state["champion_score"], -1e18)
        self.assertIn("DEAD CHAMPION RECYCLED", state["lineage_note"])

    def test_N_forced_frequency_restoration_covers_all_levels(self):
        """TEST N (anti-stall circuit breaker): every repair level has a
        deterministic forced mutation so the loop can never idle."""
        for lvl in ["L1_PARAMETER", "L2_SESSION_TIME", "L3_INDICATOR_LOGIC",
                    "L4_ARCHITECTURE", "L5_PIVOT_NEW_ALPHA"]:
            self.assertIn(lvl, FORCED_FREQUENCY_RESTORATION)
            self.assertTrue(len(FORCED_FREQUENCY_RESTORATION[lvl]) > 20)

    def test_P_mutation_diff_detector_catches_noop_children(self):
        """TEST P (anti no-op): verbatim-parent children must be detected so the
        engine never burns a physical MT5 run re-measuring the parent
        (observed live: 7 consecutive identical 8-trade reports)."""
        parent = "int OnInit(){return 0;}\nvoid OnTick(){\n   double x = 1.0;\n}\n"
        identical = "int OnInit(){return 0;}\nvoid OnTick(){\n   double x = 1.0;\n}\n"
        mutated  = "int OnInit(){return 0;}\nvoid OnTick(){\n   double x = 0.5;\n}\n"
        self.assertEqual(count_mutation_diff(parent, identical), 0)
        self.assertGreaterEqual(count_mutation_diff(parent, mutated), 2)

    def test_O_population_enrichment_full_wr_rr_buckets(self):
        """TEST O (enrichment): full-population enrichment computes WR, avgR,
        realized RR and expectancy per GMT hour across ALL trades (not just
        losers), and refuses to fabricate on tiny samples."""
        df = _df(12)
        df["gmt_hour"] = [8, 8, 8, 9, 9, 9, 10, 10, 10, 11, 11, 11]
        enr = compute_population_enrichment(df)
        self.assertIsNotNone(enr)
        self.assertEqual(enr["population_n"], 12)
        self.assertAlmostEqual(enr["overall"]["win_rate"], 0.5, places=3)
        self.assertEqual(enr["overall"]["realized_RR"], 1.0)
        self.assertIn(8, enr["by_gmt_hour"])
        self.assertIn("WR=", format_population_enrichment_block(enr))
        # Fabrication guard: N < 5 -> unavailable
        self.assertIsNone(compute_population_enrichment(_df(3)))
        self.assertIn("unavailable", format_population_enrichment_block(None))

    def test_Q_landscape_mapping_builds_from_measured_region(self):
        """TEST Q (builder mode): landscape mapping sweeps numeric inputs via
        physical runs (mocked), adopts the frequency-first best region, and
        patches input defaults into code deterministically."""
        code = ('input double InpMinBreakATR = 0.15;   // comment preserved\n'
                'input int    InpMaxBarsOutside = 8;\n'
                'input long   InpMagic = 260101;\n')
        patched = apply_params_to_code(code, {"InpMinBreakATR": 0.4, "InpMaxBarsOutside": 16})
        self.assertIn("InpMinBreakATR = 0.4;", patched)
        self.assertIn("// comment preserved", patched)
        self.assertIn("InpMaxBarsOutside = 16;", patched)
        self.assertNotIn("InpMagic = 260100", patched)

        # Mock the physical runner: widening InpMinBreakATR to its range STOP
        # yields the best frequency + fitness region.
        calls = []
        def fake_run(module, code_arg, params=None):
            calls.append(dict(params or {}))
            v = (params or {}).get("InpMinBreakATR", 0.15)
            good = abs(v - 0.225) < 1e-9  # stop = 0.15 * 1.5
            metrics = {"total_trades": 30 if good else 6,
                       "win_rate": 0.6 if good else 0.3,
                       "profit_factor": 1.8 if good else 0.9,
                       "max_drawdown": 0.05}
            return metrics, pd.DataFrame({"R": [1.0, -1.0] * 15}), Path("rep.htm")

        orig = console_mod.run_real_vantage_backtest
        console_mod.run_real_vantage_backtest = fake_run
        try:
            out = console_mod.run_landscape_mapping("MOD_X", code, max_runs=16)
        finally:
            console_mod.run_real_vantage_backtest = orig
        self.assertIsNotNone(out)
        self.assertEqual(out["params"]["InpMinBreakATR"], 0.225)
        self.assertEqual(out["metrics"]["total_trades"], 30)
        self.assertGreater(len(calls), 2)  # actually swept, not single-shot


if __name__ == "__main__":
    unittest.main()
