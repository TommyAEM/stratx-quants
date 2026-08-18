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
    run_walkforward_validation,
    enforce_memory_commitment,
    evaluate_final_portfolio_gates,
    format_population_enrichment_block,
    is_dead_population,
    pre_compute_debunked_gate,
    run_governor_decision,
    run_independent_review,
    safe_parse_json,
    check_pass_gates,
    rank_theses_by_discovery,
    build_evidence_derived_directive,
    find_impossible_breakout_triggers,
    is_hopeless_thesis,
    MODULE_MIN_TRADES_PER_YEAR,
    CHAMPION_MIN_TRADES,
    AUTHORITATIVE_GATES,
)
from orchestrator.prototype_lab import simulate_pdc, metrics_from_r, viable_region
import orchestrator.stratx_live_console as console_mod
from orchestrator.stratx_goal_loop import StratXGoalLoopOrchestrator
from skills.self_review_engine import SelfReviewEngine
from orchestrator.edge_discovery import (
    _binom_tail_pvalue,
    _bh_fdr,
    format_edge_screen_block,
    screen_open_momentum,
    load_bars,
)


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

    def test_N_authoritative_gates_consistency(self):
        """TEST N: Authoritative gates single source of truth verification."""
        self.assertEqual(AUTHORITATIVE_GATES["MODULE_CANONICAL_MAX_DD"], 0.06)
        self.assertEqual(AUTHORITATIVE_GATES["PORTFOLIO_COMBINED_MAX_DD"], 0.10)
        self.assertEqual(AUTHORITATIVE_GATES["MIN_TRADES_ANNUAL"], 20.0)
        self.assertEqual(AUTHORITATIVE_GATES["MODULE_CANONICAL_MIN_PF"], 2.00)
        self.assertEqual(AUTHORITATIVE_GATES["MODULE_CANONICAL_MIN_WR"], 0.70)

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
        Path("C:/Trading/DE40-Research/evidence/landscape_map_MOD_X.json").unlink(missing_ok=True)

    def test_R_truncated_mql5_fence_is_salvaged(self):
        """TEST R (anti no-op root cause): a reasoning-model response whose
        ```mql5 fence was truncated mid-file by max_tokens must still yield
        mql5_code (compile-fix loop repairs it) instead of silently reverting
        the child to parent code."""
        big_code = "// header\nint OnInit(){return 0;}\nvoid OnTick(){\n" + ("   double x = 1.0;\n" * 40)
        truncated = "Here is the mutated EA:\n```mql5\n" + big_code  # no closing fence
        res = safe_parse_json(truncated, default_role="MQL5 ARCHITECT")
        self.assertIn("mql5_code", res)
        self.assertIn("OnTick", res["mql5_code"])
        self.assertEqual(res.get("llm_status"), "PARSE_RECOVERED_TRUNCATED_FENCE")
        # Closed fences still take the normal path
        closed = "```mql5\n" + big_code + "\n```"
        res2 = safe_parse_json(closed, default_role="MQL5 ARCHITECT")
        self.assertIn("mql5_code", res2)

    def test_S_walkforward_anchored_oos_gate(self):
        """TEST S (Validation Engineer): anchored walk-forward requires >=2 of 3
        OOS windows within 80% decay tolerance, real OOS populations, and no
        catastrophic collapse — using mocked physical runs per window."""
        def make_mocks(is_pfs, oos_pfs, oos_trades):
            seq = []
            for i in range(3):
                seq.append({"total_trades": 20, "profit_factor": is_pfs[i]})
                seq.append({"total_trades": oos_trades[i], "profit_factor": oos_pfs[i]})
            it = iter(seq)
            return (lambda *a, **k: Path("rep.htm"),
                    lambda *a, **k: next(it))

        # PASS case: all windows hold within tolerance
        rb, pr = make_mocks([2.0, 2.0, 2.0], [1.8, 1.7, 1.9], [5, 6, 4])
        orig_rb, orig_pr = console_mod.run_mt5_backtest, console_mod.parse_mt5_report
        orig_comp = console_mod.write_and_compile_mql5
        console_mod.run_mt5_backtest, console_mod.parse_mt5_report = rb, pr
        console_mod.write_and_compile_mql5 = lambda *a, **k: (True, "ok")
        try:
            out = run_walkforward_validation("MOD_WF", "code")
            self.assertTrue(out["passed"])
            self.assertEqual(out["passing_windows"], 3)

            # FAIL case: catastrophic OOS collapse in one window
            rb2, pr2 = make_mocks([2.0, 2.0, 2.0], [1.8, 0.3, 1.9], [5, 6, 4])
            console_mod.run_mt5_backtest, console_mod.parse_mt5_report = rb2, pr2
            out2 = run_walkforward_validation("MOD_WF", "code")
            self.assertFalse(out2["passed"])
            self.assertIn("catastrophic", out2["reason"])

            # FAIL case: OOS population too small to be evidence
            rb3, pr3 = make_mocks([2.0, 2.0, 2.0], [1.8, 1.8, 1.8], [5, 1, 2])
            console_mod.run_mt5_backtest, console_mod.parse_mt5_report = rb3, pr3
            out3 = run_walkforward_validation("MOD_WF", "code")
            self.assertFalse(out3["passed"])
        finally:
            console_mod.run_mt5_backtest = orig_rb
            console_mod.parse_mt5_report = orig_pr
            console_mod.write_and_compile_mql5 = orig_comp

    def test_T_edge_discovery_screen_math(self):
        """TEST T (PHASE_0 discovery): binomial tail, BH-FDR, screen formatting,
        and real-data sanity (the screen must find occurrences on real bars and
        must NOT fabricate significance)."""
        # Binomial tail sanity
        self.assertAlmostEqual(_binom_tail_pvalue(0, 5), 1.0)
        self.assertLess(_binom_tail_pvalue(9, 10), 0.02)
        self.assertGreater(_binom_tail_pvalue(3, 10), 0.5)
        self.assertLessEqual(_binom_tail_pvalue(700, 1400), 1.0)  # large-n path
        # BH-FDR: only genuinely tiny p-values flagged
        flags = _bh_fdr([0.001, 0.40, 0.90])
        self.assertEqual(flags, [True, False, False])
        # Real-data screen: open momentum finds occurrences, honest p-value
        df = load_bars()
        self.assertGreater(len(df), 20000)
        om = screen_open_momentum(df, 9, "TEST_OPEN")
        self.assertGreater(om["occurrences"], 100)
        self.assertTrue(0.0 <= om["p_value"] <= 1.0)
        # Formatter never crashes on empty
        self.assertIn("not run", format_edge_screen_block(None))
        block = format_edge_screen_block({"data": {"bars": 10, "from": "2023-01-01", "to": "2023-02-01"},
                                          "ranked_edges": []})
        self.assertIn("No anomaly candidate", block)

    def test_U_discovery_driven_incubation_order(self):
        """TEST U (PHASE_0 -> PHASE_1 handoff): the incubation queue must be
        reordered by MEASURED support, deterministically.
        - A CONTINUATION thesis whose reversal screen measured strongly
          negative must rank FIRST (support = -mean_fwd_atr > 0, n >= 100).
        - A thesis trading in the screened direction only ranks first when
          the screen itself is positive.
        - Unsupported theses keep their original relative order.
        - No screen / no probe / tiny sample -> original order, empty report."""
        screen = {"screens": [
            {"screen": "PREV_DAY_HL_SWEEP_REVERSAL", "occurrences": 991,
             "win_rate": 0.4541, "mean_fwd_atr": -0.402, "p_value": 0.998},
            {"screen": "ASIA_FAKEOUT_REVERSAL (clock=as-is)", "occurrences": 1765,
             "win_rate": 0.472, "mean_fwd_atr": 0.005, "p_value": 0.991},
        ]}
        theses = [
            {"name": "AAA_LEGACY"},  # no probe
            {"name": "BBB_FADE", "screen_probe": "ASIA_FAKEOUT_REVERSAL"},  # direction = screened (fade); screen ~zero -> unsupported
            {"name": "CCC_PDC", "screen_probe": "PREV_DAY_HL_SWEEP_REVERSAL", "screen_direction": "CONTINUATION"},
            {"name": "DDD_TRAIL"},
        ]
        ordered, report = rank_theses_by_discovery(theses, screen)
        self.assertEqual([t["name"] for t in ordered],
                         ["CCC_PDC", "AAA_LEGACY", "BBB_FADE", "DDD_TRAIL"])
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["name"], "CCC_PDC")
        self.assertAlmostEqual(report[0]["support"], 0.402, places=3)
        # Prefix matching: probe matches screen name with a suffix
        self.assertEqual(report[0]["screen"]["screen"], "PREV_DAY_HL_SWEEP_REVERSAL")
        # In-direction thesis only boosted when screen is positive
        screen_pos = {"screens": [{"screen": "PROBE_X", "occurrences": 500,
                                   "win_rate": 0.56, "mean_fwd_atr": 0.31, "p_value": 0.01}]}
        t2 = [{"name": "ZZZ"}, {"name": "DIR", "screen_probe": "PROBE_X"}]
        o2, r2 = rank_theses_by_discovery(t2, screen_pos)
        self.assertEqual([t["name"] for t in o2], ["DIR", "ZZZ"])
        self.assertAlmostEqual(r2[0]["support"], 0.31, places=3)
        # In-direction thesis NOT boosted when screen is negative (anti-edge)
        screen_neg = {"screens": [{"screen": "PROBE_X", "occurrences": 500,
                                   "win_rate": 0.44, "mean_fwd_atr": -0.31, "p_value": 0.99}]}
        o3, r3 = rank_theses_by_discovery(t2, screen_neg)
        self.assertEqual([t["name"] for t in o3], ["ZZZ", "DIR"])
        self.assertEqual(r3, [])
        # Sub-material effect (0.005 ATR, huge n) -> NO boost: noise is not an edge
        screen_noise = {"screens": [{"screen": "PROBE_X", "occurrences": 5000,
                                     "win_rate": 0.51, "mean_fwd_atr": 0.005, "p_value": 0.30}]}
        o3b, r3b = rank_theses_by_discovery(t2, screen_noise)
        self.assertEqual([t["name"] for t in o3b], ["ZZZ", "DIR"])
        self.assertEqual(r3b, [])
        # Small sample -> no boost even with big effect
        screen_tiny = {"screens": [{"screen": "PROBE_X", "occurrences": 12,
                                    "win_rate": 0.9, "mean_fwd_atr": 2.0, "p_value": 0.001}]}
        o4, r4 = rank_theses_by_discovery(t2, screen_tiny)
        self.assertEqual([t["name"] for t in o4], ["ZZZ", "DIR"])
        self.assertEqual(r4, [])
        # No screen at all -> untouched order, empty report
        o5, r5 = rank_theses_by_discovery(theses, None)
        self.assertEqual([t["name"] for t in o5],
                         ["AAA_LEGACY", "BBB_FADE", "CCC_PDC", "DDD_TRAIL"])
        self.assertEqual(r5, [])
        # Multiple supported theses sort by descending support, stable by original index
        screen_two = {"screens": [
            {"screen": "P1", "occurrences": 300, "mean_fwd_atr": 0.20, "win_rate": 0.55, "p_value": 0.01},
            {"screen": "P2", "occurrences": 300, "mean_fwd_atr": 0.50, "win_rate": 0.58, "p_value": 0.001},
        ]}
        t6 = [{"name": "FIRST", "screen_probe": "P1"},
              {"name": "MID"},
              {"name": "SECOND", "screen_probe": "P2"}]
        o6, r6 = rank_theses_by_discovery(t6, screen_two)
        self.assertEqual([t["name"] for t in o6], ["SECOND", "FIRST", "MID"])
        self.assertEqual([r["name"] for r in r6], ["SECOND", "FIRST"])

    def test_V_evidence_derived_antistall_directive(self):
        """TEST V (no repair recipes): the anti-stall forced directive must be
        derived from the MEASURED failure map — naming the diagnosis and citing
        the numbers — never a predefined trading solution. Deterministic."""
        # Dead population -> population collapse directive
        d1 = build_evidence_derived_directive("L1_PARAMETER", "FREQUENCY_COLLAPSE",
                                              {"total_trades": 3, "win_rate": 0.0, "profit_factor": 0.0})
        self.assertIn("POPULATION COLLAPSE", d1)
        self.assertIn("N=3", d1)
        # Catastrophic drawdown on a live population -> drawdown tail, cites numbers
        dd_metrics = {"total_trades": 1272, "win_rate": 0.741, "profit_factor": 1.16,
                      "max_drawdown": 0.256, "max_consecutive_losses": 5}
        d2 = build_evidence_derived_directive("L3_INDICATOR_LOGIC", None, dd_metrics)
        self.assertIn("DRAWDOWN TAIL", d2)
        self.assertIn("25.6%", d2)
        self.assertIn("frequency restoration is FORBIDDEN", d2)
        # Payoff asymmetry: high WR, weak PF -> payoff directive with implied R
        pa_metrics = {"total_trades": 400, "win_rate": 0.74, "profit_factor": 1.16,
                      "max_drawdown": 0.08, "max_consecutive_losses": 3}
        d3 = build_evidence_derived_directive("L2_SESSION_TIME", None, pa_metrics)
        self.assertIn("PAYOFF ASYMMETRY", d3)
        self.assertIn("~0.41R", d3)  # 1.16 * 0.26 / 0.74 = 0.4076
        # Loss clustering beats weak-edge branch when consec above ceiling
        lc_metrics = {"total_trades": 300, "win_rate": 0.55, "profit_factor": 1.20,
                      "max_drawdown": 0.08, "max_consecutive_losses": 9}
        d4 = build_evidence_derived_directive("L1_PARAMETER", None, lc_metrics)
        self.assertIn("LOSS CLUSTERING", d4)
        # Weak edge
        d5 = build_evidence_derived_directive("L1_PARAMETER", None,
                                              {"total_trades": 200, "win_rate": 0.52, "profit_factor": 1.20,
                                               "max_drawdown": 0.05, "max_consecutive_losses": 4})
        self.assertIn("WEAK EDGE", d5)
        # Near-canonical -> unmet-gates directive
        d6 = build_evidence_derived_directive("L4_ARCHITECTURE", None,
                                              {"total_trades": 300, "win_rate": 0.66, "profit_factor": 1.80,
                                               "max_drawdown": 0.05, "max_consecutive_losses": 3})
        self.assertIn("CANONICAL GATES UNMET", d6)
        # NO PREDEFINED RECIPES anywhere in any branch
        banned = ["session widening", "runner capture", "indicator relaxation",
                  "loosen the tightest", "expand the active trading window",
                  "drop one filter entirely", "inverting the thesis"]
        for d in (d1, d2, d3, d4, d5, d6):
            for b in banned:
                self.assertNotIn(b, d.lower())
        # Deterministic
        self.assertEqual(d2, build_evidence_derived_directive("L3_INDICATOR_LOGIC", None, dd_metrics))
        # Gates sourced from the authoritative config
        self.assertIn(f"{AUTHORITATIVE_GATES['RESEARCH_INCUMBENT_MAX_DD']*100:.0f}%", d2)
        self.assertEqual(AUTHORITATIVE_GATES["MODULE_CANONICAL_MIN_RR"], 1.00)

    def test_W_child_reforensics_hard_block(self):
        """TEST W (P0.2/P0.6): a review routing CHILD_REFORENSICS_REQUIRED must
        block the next generation until a fresh child failure map exists —
        enforced by validate_workflow_gates, completed by an actual forensics
        record. History showed required=true/completed=false while later
        iterations ran; this test proves that state is now a hard violation."""
        engine = SelfReviewEngine()
        review_record = {
            "implementation_fidelity": "MATCH",
            "experiment_design_quality": "VALID",
            "recommended_route": "CHILD_REFORENSICS_REQUIRED",
            "workflow_gates": {"self_review_completed": True,
                               "child_reforensics_required": True,
                               "child_reforensics_completed": False},
        }
        # No reforensics record -> mutation FORBIDDEN
        out = engine.validate_workflow_gates({}, review_record, None)
        self.assertFalse(out["is_allowed"])
        self.assertTrue(any("CHILD_REFORENSICS" in v for v in out["violations"]))
        # The completed flag alone is not enough — an actual record must exist
        review_record["workflow_gates"]["child_reforensics_completed"] = True
        out2 = engine.validate_workflow_gates({}, review_record, None)
        self.assertFalse(out2["is_allowed"])
        # Actual fresh forensics record -> block released
        reforensics_record = {"iteration": 2, "module": "MOD", "population_n": 42,
                              "enrichment_available": True, "matched_winner_available": True}
        out3 = engine.validate_workflow_gates({}, review_record, reforensics_record)
        self.assertTrue(out3["is_allowed"])
        # A non-required route never blocks
        review_record["recommended_route"] = "CONTINUE"
        out4 = engine.validate_workflow_gates({}, review_record, None)
        self.assertTrue(out4["is_allowed"])

    def test_X_dead_template_linter(self):
        """TEST X (impossible-breakout class): a Donchian/BOS channel that
        INCLUDES the signal bar (iHighest/iLowest start shift 1) compared
        against that bar's close can never fire — observed live as Module_5
        burning L1-L5 + landscape mapping at N=0. The linter must catch the
        pre-fix pattern and pass all shipped module templates."""
        buggy = ("int h = iHighest(_Symbol, PERIOD_H1, MODE_HIGH, 20, 1);\n"
                 "double d_high = iHigh(_Symbol, PERIOD_H1, h);\n"
                 "if(iClose(_Symbol, PERIOD_H1, 1) > d_high) { OpenBuy(); }")
        findings = find_impossible_breakout_triggers(buggy)
        self.assertTrue(any("IMPOSSIBLE LONG BREAKOUT" in f for f in findings))
        buggy_short = ("int l = iLowest(_Symbol, _Period, MODE_LOW, 20, 1);\n"
                       "double d_low = iLow(_Symbol, _Period, l);\n"
                       "if(iClose(_Symbol, _Period, 1) < d_low) { OpenSell(); }")
        findings_s = find_impossible_breakout_triggers(buggy_short)
        self.assertTrue(any("IMPOSSIBLE SHORT BREAKOUT" in f for f in findings_s))
        # fixed pattern (channel excludes signal bar) is clean
        fixed = buggy.replace("MODE_HIGH, 20, 1)", "MODE_HIGH, 20, 2)")
        self.assertEqual(find_impossible_breakout_triggers(fixed), [])
        # fib-style usage (extremes define levels, not breakout barriers) is clean
        fib = ("int h = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, 50, 1);\n"
               "double swing_high = iHigh(_Symbol, PERIOD_CURRENT, h);\n"
               "if(iClose(_Symbol, PERIOD_CURRENT, 1) > fib_618) { OpenBuy(); }")
        self.assertEqual(find_impossible_breakout_triggers(fib), [])
        # every shipped module template must pass (thesis list is function-local;
        # extract it from source exactly as the runtime defines it)
        import re as _re
        src = open(str(Path(console_mod.__file__)), encoding="utf-8").read()
        i = src.find("MODULE_THESES = [")
        j = src.find("\n        ]", i)
        theses = eval(src[i + len("MODULE_THESES = "):j + len("\n        ]")])
        self.assertGreaterEqual(len(theses), 10)
        for t in theses:
            self.assertEqual(find_impossible_breakout_triggers(t.get("base_code", "")), [],
                             f"{t.get('name')} ships an impossible breakout trigger")

    def test_Y_prototype_lab(self):
        """TEST Y (STAGE 1 prototype): deterministic R-accounting and PDC
        simulation semantics on synthetic bars — fixed RR geometry, stop-first
        conservatism, one-position-at-a-time, viable-region thresholds."""
        m = metrics_from_r([2.0, 2.0, -1.0, -1.0, 3.0], pd.DataFrame({"date": [pd.Timestamp("2024-01-01").date(), pd.Timestamp("2024-12-31").date()]}))
        self.assertAlmostEqual(m["profit_factor"], round(7.0 / 2.0, 3))
        self.assertAlmostEqual(m["win_rate"], 0.6)
        self.assertEqual(m["n"], 5)
        self.assertGreaterEqual(m["max_dd_r"], 2.0)
        self.assertEqual(metrics_from_r([], pd.DataFrame({"date": [pd.Timestamp("2024-01-01").date(), pd.Timestamp("2024-01-02").date()]}))["n"], 0)
        # synthetic bars: two prior days range 100-110; signal day 09:00 closes
        # at 111 with displacement body; entry next open; 2R target hit first
        rows = []
        base = pd.Timestamp("2024-01-02 08:00")
        for d in range(2):
            day = base + pd.Timedelta(days=d)
            for b in range(8):
                rows.append({"time": day + pd.Timedelta(minutes=15 * b),
                             "open": 105.0, "high": 110.0, "low": 100.0, "close": 105.0})
        sig_day = base + pd.Timedelta(days=2)
        rows.append({"time": sig_day.replace(hour=9), "open": 105.0, "high": 111.5, "low": 104.5, "close": 111.0})
        rows.append({"time": sig_day.replace(hour=9, minute=15), "open": 111.2, "high": 113.0, "low": 110.8, "close": 112.5})
        rows.append({"time": sig_day.replace(hour=9, minute=30), "open": 112.5, "high": 117.0, "low": 112.0, "close": 116.5})
        df = pd.DataFrame(rows)
        df["atr"] = 2.0
        df["date"] = df["time"].dt.date
        df["hour"] = df["time"].dt.hour
        out = simulate_pdc(df, stop_atr=1.0, target_rr=2.0, min_beyond_atr=0.05,
                           disp_body_atr=0.3, max_ext_atr=3.0, start_hour=7, end_hour=12,
                           max_daily_losses=0, cost_r=0.0)
        self.assertEqual(out["n"], 1)
        self.assertEqual(out["win_rate"], 1.0)
        self.assertAlmostEqual(out["total_r"], 2.0)
        grid = [{"n": 206, "profit_factor": 1.42, "expectancy_r": 0.30},
                {"n": 50, "profit_factor": 2.50, "expectancy_r": 0.90}]
        self.assertEqual(viable_region(grid)["n"], 206)
        self.assertIsNone(viable_region([{"n": 500, "profit_factor": 1.10, "expectancy_r": 0.02}]))

    def test_Z_hopeless_thesis_kill_gate(self):
        """TEST Z (anti turd-polishing + RR hard floor): theses whose best
        measured population is net-negative or losing on both axes are dead
        on arrival; high-RR profiles survive; the directive names the floor."""
        self.assertFalse(is_hopeless_thesis(None))
        self.assertFalse(is_hopeless_thesis({"total_trades": 7, "profit_factor": 0.5}))
        self.assertTrue(is_hopeless_thesis({"total_trades": 155, "win_rate": 0.316,
                                            "profit_factor": 0.90, "risk_reward": 1.9}))
        self.assertTrue(is_hopeless_thesis({"total_trades": 100, "win_rate": 0.40,
                                            "profit_factor": 1.05, "risk_reward": 0.8}))
        self.assertFalse(is_hopeless_thesis({"total_trades": 100, "win_rate": 0.34,
                                             "profit_factor": 1.42, "risk_reward": 2.7}))
        self.assertFalse(is_hopeless_thesis({"total_trades": 100, "win_rate": 0.65,
                                             "profit_factor": 1.20, "risk_reward": 1.1}))
        d = build_evidence_derived_directive("L3_INDICATOR_LOGIC", None,
                                             {"total_trades": 400, "win_rate": 0.74, "profit_factor": 1.16,
                                              "max_drawdown": 0.05, "max_consecutive_losses": 3,
                                              "risk_reward": 0.41})
        self.assertIn("PAYOFF BELOW HARD FLOOR", d)
        self.assertIn("auto-rejected", d)
        self.assertEqual(AUTHORITATIVE_GATES["RESEARCH_INCUMBENT_MIN_RR"], 1.00)


if __name__ == "__main__":
    unittest.main()
