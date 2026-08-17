"""
StratX Quant Skills — Comprehensive Unit & Regression Test Suite
Tests all 16 quantitative scientific skills deterministically.
"""

import sys
import unittest
from pathlib import Path

# Add skills dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills import (
    TradePopulationAnalyzer,
    ClusterDetector,
    RegimeTagger,
    CausalDecomposer,
    FailureModeClassifier,
    HypothesisEvidenceEngine,
    ChildParentDelta,
    StructuralMutationEngine,
    ParameterLandscapeExplorer,
    OverfittingGuard,
    ResearchPolicyLearner,
    EvidenceDependencyGraph,
    ResearchMapEIVEngine,
    ResearchExhaustionEngine,
    PortfolioGapAnalyzer,
    SelfReviewEngine
)

class TestQuantSkillsSuite(unittest.TestCase):

    def setUp(self):
        # Sample synthetic trade population
        self.sample_trades = [
            {"position_id": "T1", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-10 08:30:00", "net_profit": 150.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 1.4, "f_rel_vol": 1.2}},
            {"position_id": "T2", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-10 09:15:00", "net_profit": 120.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 1.2, "f_rel_vol": 1.1}},
            {"position_id": "T3", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-10 10:00:00", "net_profit": -100.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 0.4, "f_rel_vol": 0.6}},
            {"position_id": "T4", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-11 08:45:00", "net_profit": -100.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 0.5, "f_rel_vol": 0.5}},
            {"position_id": "T5", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-11 09:30:00", "net_profit": -100.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 0.3, "f_rel_vol": 0.4}},
            {"position_id": "T6", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-12 14:00:00", "net_profit": 140.0, "R0": 100.0, "session": "US_OVERLAP", "features": {"f_disp": 1.5, "f_rel_vol": 1.3}},
            {"position_id": "T7", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-12 15:00:00", "net_profit": 110.0, "R0": 100.0, "session": "US_OVERLAP", "features": {"f_disp": 1.1, "f_rel_vol": 1.0}},
            {"position_id": "T8", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-15 08:30:00", "net_profit": 130.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 1.3, "f_rel_vol": 1.2}},
            {"position_id": "T9", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-15 09:00:00", "net_profit": -100.0, "R0": 100.0, "session": "LONDON_OPEN", "features": {"f_disp": 0.6, "f_rel_vol": 0.7}},
            {"position_id": "T10", "symbol": "DE40", "direction": "LONG", "entry_time": "2024-01-15 14:30:00", "net_profit": 150.0, "R0": 100.0, "session": "US_OVERLAP", "features": {"f_disp": 1.6, "f_rel_vol": 1.4}}
        ]

    # TEST SKILL 1: Canonical Trade Population Engine
    def test_trade_population_analyzer(self):
        analyzer = TradePopulationAnalyzer()
        res = analyzer.analyze_trades(self.sample_trades)
        self.assertEqual(res["status"], "SUCCESS")
        metrics = res["metrics"]
        self.assertEqual(metrics["trade_count"], 10)
        self.assertEqual(metrics["win_count"], 6)
        self.assertEqual(metrics["loss_count"], 4)
        self.assertEqual(metrics["win_rate"], 0.6)
        self.assertEqual(metrics["accounting_status"], "VALID")

    # TEST SKILL 2: Cluster Detector
    def test_cluster_detector(self):
        analyzer = TradePopulationAnalyzer()
        pop = analyzer.analyze_trades(self.sample_trades)["positions"]
        detector = ClusterDetector(min_cluster_size=3, min_effect_size=0.05, max_nominal_p=0.30)
        res = detector.detect_clusters(pop)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreaterEqual(res["clusters_found"], 1)

    # TEST SKILL 3: Point-in-Time Regime Tagger
    def test_regime_tagger(self):
        tagger = RegimeTagger()
        trade = {"entry_time": "2024-01-10 08:30:00", "trade_R": 1.2, "features": {"f_disp": 1.4, "atr_pct": 80.0}}
        tagged = tagger.tag_trade(trade)
        self.assertEqual(tagged["session"], "LONDON_OPEN")
        self.assertEqual(tagged["regime_tags"]["volatility_regime"], "HIGH_VOL")
        self.assertEqual(tagged["regime_tags"]["tagger_version"], RegimeTagger.VERSION)

    # TEST SKILL 4: Causal Decomposition Engine
    def test_causal_decomposer(self):
        analyzer = TradePopulationAnalyzer()
        pop = analyzer.analyze_trades(self.sample_trades)["positions"]
        decomposer = CausalDecomposer(min_matched_sample=2)
        res = decomposer.decompose_factor(pop, "low_disp", lambda p: float(p.get("features", {}).get("f_disp", 1.0)) < 1.0)
        self.assertEqual(res["status"], "ANALYZED")
        self.assertGreater(res["odds_ratio_loss"], 1.0)
        self.assertIn(res["support_strength"], ["STRONG", "MODERATE", "WEAK"])

    # TEST SKILL 5: Failure Mode Classifier
    def test_failure_mode_classifier(self):
        classifier = FailureModeClassifier()
        evidence = {
            "dev_pf": 2.5,
            "val_pf": 0.85,
            "rules_added_count": 4,
            "trade_drop_pct": 50.0
        }
        res = classifier.classify_failure(evidence)
        self.assertIn("VALIDATION_COLLAPSE", res["all_categories"])
        self.assertIn("FILTER_ACCRETION", res["all_categories"])
        self.assertEqual(res["primary_failure_mode"], "VALIDATION_COLLAPSE")

    # TEST SKILL 6: Belief + Hypothesis Engine
    def test_hypothesis_evidence_engine(self):
        engine = HypothesisEvidenceEngine()
        bid = engine.create_belief("High displacement generates mean reversion edge", "DE40_VWAPX", initial_confidence=0.85)
        self.assertEqual(engine.beliefs[bid]["status"], "PROPOSED")

        # Non-destructive revision
        engine.revise_belief(bid, "WEAKENING", 0.40, "Telemetry indexing defect invalidated high-disp feature", "DEFECT_LOG_01")
        self.assertEqual(engine.beliefs[bid]["status"], "WEAKENING")
        self.assertEqual(engine.beliefs[bid]["confidence"], 0.40)
        self.assertEqual(len(engine.beliefs[bid]["revision_history"]), 1)

    # TEST SKILL 7: Child-Parent Trade Delta
    def test_child_parent_delta(self):
        parent = self.sample_trades
        child = [p for p in self.sample_trades if p["position_id"] not in ["T3", "T4"]]
        delta_eng = ChildParentDelta()
        res = delta_eng.compute_delta(parent, child)
        self.assertEqual(res["parent_trade_count"], 10)
        self.assertEqual(res["child_trade_count"], 8)
        self.assertEqual(res["losers_removed_count"], 2)
        self.assertEqual(res["winners_removed_count"], 0)
        self.assertTrue(res["net_beneficial_filter"])

    # TEST SKILL 8: Structural Mutation Engine & Validator
    def test_structural_mutation_engine(self):
        engine = StructuralMutationEngine()
        spec = engine.create_experiment_spec(
            experiment_id="EXP_001",
            parent_strategy_id="VWAPX_PARENT",
            hypothesis_id="HYP_01",
            repair_level="L2_RULE",
            market_thesis="Filter midday noise",
            parameter_changes={"InpMinDisp": 1.2, "InpSessionMask": 2}
        )
        self.assertTrue(bool(spec["spec_hash"]))

        # Matching implementation receipt
        receipt_good = engine.create_implementation_receipt(
            experiment_id="EXP_001",
            source_path="ea/test.mq5",
            source_content="input double InpMinDisp = 1.2;",
            set_content="InpMinDisp=1.2\nInpSessionMask=2",
            implemented_params={"InpMinDisp": 1.2, "InpSessionMask": 2},
            compile_success=True
        )
        val_res = engine.validate_implementation(spec, receipt_good)
        self.assertTrue(val_res["is_valid"])
        self.assertEqual(val_res["status"], "APPROVED")

        # Mismatched receipt (missing param)
        receipt_bad = engine.create_implementation_receipt(
            experiment_id="EXP_001",
            source_path="ea/test.mq5",
            source_content="input double InpMinDisp = 0.5;",
            set_content="InpMinDisp=0.5",
            implemented_params={"InpMinDisp": 0.5},
            compile_success=True
        )
        val_bad = engine.validate_implementation(spec, receipt_bad)
        self.assertFalse(val_bad["is_valid"])
        self.assertEqual(val_bad["status"], "IMPLEMENTATION_FAILURE")

    # TEST SKILL 9: Parameter Landscape Explorer
    def test_parameter_landscape_explorer(self):
        explorer = ParameterLandscapeExplorer()
        grid_plateau = [
            {"param_val": 1.0, "profit_factor": 1.8},
            {"param_val": 1.2, "profit_factor": 2.0},
            {"param_val": 1.4, "profit_factor": 2.1},
            {"param_val": 1.6, "profit_factor": 2.05},
            {"param_val": 1.8, "profit_factor": 1.9}
        ]
        res_plateau = explorer.analyze_surface("InpMinDisp", grid_plateau)
        self.assertTrue(res_plateau["is_robust_plateau"])
        self.assertIn("PLATEAU", res_plateau["classification"])

        grid_spike = [
            {"param_val": 1.0, "profit_factor": 0.8},
            {"param_val": 1.2, "profit_factor": 0.9},
            {"param_val": 1.4, "profit_factor": 3.5},
            {"param_val": 1.6, "profit_factor": 0.7},
            {"param_val": 1.8, "profit_factor": 0.6}
        ]
        res_spike = explorer.analyze_surface("InpMinDisp", grid_spike)
        self.assertFalse(res_spike["is_robust_plateau"])
        self.assertEqual(res_spike["recommendation"], "REJECT_OVERFIT_SPIKE")

    # TEST SKILL 10: Overfitting Guard
    def test_overfitting_guard(self):
        guard = OverfittingGuard()
        dev_good = {"profit_factor": 2.4, "win_rate": 0.65, "trade_count": 80}
        val_good = {"profit_factor": 2.1, "win_rate": 0.62, "trade_count": 35}
        audit_pass = guard.audit_partition_generalization(dev_good, val_good, trial_count=3)
        self.assertTrue(audit_pass["passed_generalization"])
        self.assertEqual(audit_pass["verdict"], "VALIDATION_PASSED")

        val_collapsed = {"profit_factor": 0.82, "win_rate": 0.41, "trade_count": 30}
        audit_fail = guard.audit_partition_generalization(dev_good, val_collapsed, trial_count=20)
        self.assertFalse(audit_fail["passed_generalization"])
        self.assertEqual(audit_fail["verdict"], "OUT_OF_SAMPLE_COLLAPSE")

    # TEST SKILL 11: Research Policy Learner (Meta-Self-Healing)
    def test_research_policy_learner(self):
        learner = ResearchPolicyLearner()
        self.assertGreaterEqual(len(learner.get_all_policies()), 2)
        bad_action_context = {"rule_count": 4, "freq_drop_pct": 50.0}
        matches = learner.evaluate_research_action(bad_action_context)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["trigger_pattern"], "FILTER_ACCRETION_WITH_DROPPING_FREQUENCY")

    # TEST SKILL 12: Evidence Dependency Graph
    def test_evidence_dependency_graph(self):
        graph = EvidenceDependencyGraph()
        graph.add_node("FEAT_DISP_V1", "FEATURE")
        graph.add_node("OBS_01", "FORENSIC_OBSERVATION")
        graph.add_node("HYP_01", "HYPOTHESIS")
        graph.add_node("EXP_01", "EXPERIMENT")
        graph.add_node("MODULE_2", "MODULE_FREEZE")

        graph.add_dependency("FEAT_DISP_V1", "OBS_01")
        graph.add_dependency("OBS_01", "HYP_01")
        graph.add_dependency("HYP_01", "EXP_01")
        graph.add_dependency("EXP_01", "MODULE_2")

        res = graph.invalidate_node("FEAT_DISP_V1", "INDEXING_BAR_DEFECT")
        self.assertEqual(res["invalidated_count"], 5)
        self.assertEqual(graph.nodes["MODULE_2"]["status"], "INVALIDATED_INDEXING_BAR_DEFECT")

    # TEST SKILL 13: Research Map & EIV Engine
    def test_research_map_eiv(self):
        engine = ResearchMapEIVEngine()
        candidates = [
            {"family": "VWAPX", "brain_evidence": 0.85, "coverage": "LIGHT", "portfolio_gap_score": 0.90, "negative_prior_penalty": 0.05},
            {"family": "FORB", "brain_evidence": 0.40, "coverage": "EXHAUSTED", "portfolio_gap_score": 0.30, "negative_prior_penalty": 0.30}
        ]
        ranked = engine.rank_candidates(candidates)
        self.assertEqual(ranked[0]["family"], "VWAPX")
        self.assertGreater(ranked[0]["eiv_score"], ranked[1]["eiv_score"])

    # TEST SKILL 14: Research Exhaustion Engine
    def test_research_exhaustion_engine(self):
        engine = ResearchExhaustionEngine()
        ev_active = {"hypotheses_tested_count": 1, "branches_tested_count": 2, "remaining_eiv": 0.6}
        res_active = engine.evaluate_family_exhaustion("VWAPX", ev_active)
        self.assertFalse(res_active["is_exhausted"])
        self.assertEqual(res_active["status"], "RESEARCH_ACTIVE")

        ev_exhausted = {
            "hypotheses_tested_count": 4,
            "branches_tested_count": 6,
            "remaining_eiv": 0.15,
            "val_status": "REFUTED",
            "parameter_sweeps_completed": True
        }
        res_ex = engine.evaluate_family_exhaustion("FORB", ev_exhausted)
        self.assertTrue(res_ex["is_exhausted"])
        self.assertEqual(res_ex["status"], "FAMILY_EXHAUSTED_WITHIN_DEFINED_SCOPE")

    # TEST SKILL 15: Portfolio Gap Analyzer
    def test_portfolio_gap_analyzer(self):
        analyzer = PortfolioGapAnalyzer()
        frozen = [
            {"module_id": "M1_VPPOC", "alpha_type": "VALUE_AREA_FADE", "direction": "LONG", "session": "LONDON_OPEN"}
        ]
        cand_vwapx = {"module_id": "M2_VWAPX", "alpha_type": "VWAP_EXTENSION_REVERSION", "direction": "LONG", "session": "US_OVERLAP"}
        res1 = analyzer.analyze_portfolio(frozen, cand_vwapx)
        self.assertTrue(res1["candidate_evaluation"]["fills_alpha_gap"])
        self.assertGreaterEqual(res1["candidate_evaluation"]["portfolio_fit_score"], 0.7)

        cand_dup = {"module_id": "M2_VPPOC_ALT", "alpha_type": "VALUE_AREA_FADE", "direction": "LONG", "session": "LONDON_OPEN"}
        res2 = analyzer.analyze_portfolio(frozen, cand_dup)
        self.assertFalse(res2["candidate_evaluation"]["fills_alpha_gap"])
        self.assertEqual(res2["candidate_evaluation"]["recommendation"], "REDUNDANT_ALPHA_DUPLICATION")

    # TEST SKILL 16: Mandatory Self-Review Engine & Workflow Gates
    def test_self_review_engine(self):
        srev_engine = SelfReviewEngine()
        spec = {
            "experiment_id": "EXP_01",
            "parent_strategy_id": "PARENT",
            "predicted_effect": "Prune bad losers",
            "predicted_damage": "Minimal volume loss",
            "market_thesis": "Filter low displacement",
            "parameter_changes": {"InpMinDisp": 1.2}
        }
        delta = {
            "net_R_delta": 4.5,
            "losers_removed_count": 4,
            "winners_removed_count": 0,
            "frequency_retention_pct": 88.0,
            "same_trade_count": 20,
            "new_trade_count": 0
        }
        record = srev_engine.create_self_review("de40-x1x", "GEN_1", "EXP_01", "PARENT", "CHILD", spec, delta, {})
        self.assertEqual(record["prediction_match"], "CONFIRMED")
        self.assertEqual(record["target_failure_status"], "FIXED")
        self.assertEqual(record["causal_belief_update"], "SUPPORTED")
        self.assertEqual(record["recommended_route"], "CHILD_REFORENSICS_REQUIRED")

        # Verify gate check
        gate_res = srev_engine.validate_workflow_gates({}, record, {"clusters_found": 0})
        self.assertTrue(gate_res["is_allowed"])
        self.assertEqual(gate_res["status"], "APPROVED")

if __name__ == "__main__":
    unittest.main()
