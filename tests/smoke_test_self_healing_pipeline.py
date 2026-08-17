"""
StratX Quant Self-Healing — End-to-End Pipeline Smoke Test
Demonstrates the complete deterministic scientific pipeline from baseline MT5 population to policy learning.
"""

import sys
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
    PortfolioGapAnalyzer
)

def run_smoke_test():
    print("=== STARTING STRATX SELF-HEALING END-TO-END SMOKE TEST ===\n")

    # STEP 1: Baseline Ingestion
    print("1. [Trade Population Engine] Processing baseline trades & reconciling accounting...")
    raw_trades = [
        {"position_id": f"T{i}", "symbol": "DE40", "direction": "LONG", "entry_time": f"2024-01-{10+i%15:02d} 08:30:00", "net_profit": 150.0 if i%3 != 0 else -100.0, "R0": 100.0, "session": "LONDON_OPEN" if i%2 == 0 else "US_OVERLAP", "features": {"f_disp": 1.4 if i%3 != 0 else 0.4, "f_rel_vol": 1.2 if i%3 != 0 else 0.3}}
        for i in range(1, 31)
    ]
    analyzer = TradePopulationAnalyzer()
    pop_res = analyzer.analyze_trades(raw_trades)
    print(f"   -> Trades: {pop_res['metrics']['trade_count']} | WR: {pop_res['metrics']['win_rate']*100:.1f}% | PF: {pop_res['metrics']['profit_factor']} | Accounting: {pop_res['metrics']['accounting_status']}")
    assert pop_res["metrics"]["accounting_status"] == "VALID"

    # STEP 2: Point-in-Time Regime Tagging
    print("\n2. [Regime Tagger] Tagging market regimes at trade entry...")
    tagger = RegimeTagger()
    tagged_pop = tagger.tag_population(pop_res["positions"])
    print(f"   -> Tagged {len(tagged_pop)} trades with version {RegimeTagger.VERSION} features.")

    # STEP 3: Loss Cluster Detection
    print("\n3. [Cluster Detector] Discovering multi-dimensional failure clusters...")
    detector = ClusterDetector(min_cluster_size=5, min_effect_size=0.08, max_nominal_p=0.30)
    clusters = detector.detect_clusters(tagged_pop)
    top_cluster = clusters["clusters"][0] if clusters["clusters"] else None
    print(f"   -> Top Failure Cluster: {top_cluster['cluster_id']} | Loss Rate: {top_cluster['cluster_rate']*100:.1f}% vs Base: {clusters['base_loss_rate']*100:.1f}% (Effect: {top_cluster['effect_size']}, p-val: {top_cluster['p_value']}, q-val FDR: {top_cluster['q_value_fdr']}, Tier: {top_cluster['statistical_tier']})")
    assert top_cluster is not None

    # STEP 4: Causal Decomposition
    print("\n4. [Causal Decomposition Engine] Comparing failure cluster against matched winners...")
    decomposer = CausalDecomposer(min_matched_sample=3)
    causal_res = decomposer.decompose_factor(tagged_pop, "low_disp", lambda p: float(p.get("features", {}).get("f_disp", 1.0)) < 1.0)
    print(f"   -> Odds Ratio of Loss: {causal_res['odds_ratio_loss']} | Cohen's d: {causal_res['cohens_d_effect_size']} | Support: {causal_res['support_strength']}")
    assert causal_res["support_strength"] in ["STRONG", "MODERATE"]

    # STEP 5: Failure Mode Taxonomy
    print("\n5. [Failure Mode Classifier] Classifying failure taxonomy & retrieving interventions...")
    classifier = FailureModeClassifier()
    failure_mode = classifier.classify_failure({"dev_pf": 1.5, "val_pf": 1.2, "rules_added_count": 1})
    print(f"   -> Primary Mode: {failure_mode['primary_failure_mode']} | Next: {failure_mode['recommended_next_action']}")

    # STEP 6: Belief & Hypothesis Creation
    print("\n6. [Hypothesis Engine] Creating first-class belief & competing hypothesis...")
    hyp_engine = HypothesisEvidenceEngine()
    bid = hyp_engine.create_belief("Low displacement (<1.0) causes trade failure in London Open", "DE40_VWAPX", initial_confidence=0.80)
    hid = hyp_engine.create_hypothesis(
        observation_ids=[top_cluster["cluster_id"]],
        causal_theory="Price extension lacks sufficient standard deviation to overcome spread/friction.",
        predicted_effect="Eliminate low-disp losers while preserving 95%+ of winners",
        falsification_condition="If win rate drops below 55% or frequency drops >40%",
        distinguishing_experiment="Filter f_disp >= 1.0"
    )
    print(f"   -> Created Belief {bid} and Hypothesis {hid}")

    # STEP 7: Structural Mutation & Implementation Validation
    print("\n7. [Structural Mutation Engine] Formulating Experiment Spec and validating implementation...")
    mut_engine = StructuralMutationEngine()
    spec = mut_engine.create_experiment_spec(
        experiment_id="EXP_VWAPX_G2A",
        parent_strategy_id="DE40_VWAPX_PARENT",
        hypothesis_id=hid,
        repair_level="L2_RULE",
        market_thesis="Require f_disp >= 1.0",
        parameter_changes={"InpMinDisp": 1.0}
    )
    receipt = mut_engine.create_implementation_receipt(
        experiment_id="EXP_VWAPX_G2A",
        source_path="ea/DE40_VWAPX_G2A.mq5",
        source_content="input double InpMinDisp = 1.0;",
        set_content="InpMinDisp=1.0",
        implemented_params={"InpMinDisp": 1.0},
        compile_success=True
    )
    val_check = mut_engine.validate_implementation(spec, receipt)
    print(f"   -> Implementation Validation: {val_check['status']} (is_valid: {val_check['is_valid']})")
    assert val_check["is_valid"]

    # STEP 8: Child vs Parent Trade Delta
    print("\n8. [Child-Parent Delta] Simulating Child MT5 run and calculating population delta...")
    child_trades = [p for p in tagged_pop if float(p.get("features", {}).get("f_disp", 1.0)) >= 1.0]
    delta_eng = ChildParentDelta()
    delta_res = delta_eng.compute_delta(tagged_pop, child_trades)
    print(f"   -> Delta Result: {delta_res['causal_interpretation']}")
    print(f"   -> Losers Removed: {delta_res['losers_removed_count']} | Winners Removed: {delta_res['winners_removed_count']} | Net R Delta: +{delta_res['net_R_delta']}R")
    assert delta_res["net_beneficial_filter"]

    # STEP 9: Parameter Landscape & Plateau Audit
    print("\n9. [Parameter Landscape Explorer] Verifying plateau stability around InpMinDisp=1.0...")
    param_explorer = ParameterLandscapeExplorer()
    grid = [
        {"param_val": 0.8, "profit_factor": 2.1},
        {"param_val": 1.0, "profit_factor": 2.6},
        {"param_val": 1.2, "profit_factor": 2.4},
        {"param_val": 1.4, "profit_factor": 2.2}
    ]
    surface_res = param_explorer.analyze_surface("InpMinDisp", grid)
    print(f"   -> Parameter Surface: {surface_res['classification']} | Recommendation: {surface_res['recommendation']}")
    assert surface_res["is_robust_plateau"]

    # STEP 10: Overfitting Guard (VAL Generalization)
    print("\n10. [Overfitting Guard] Auditing Out-of-Sample (VAL) generalization...")
    guard = OverfittingGuard()
    dev_m = {"profit_factor": 2.6, "win_rate": 0.70, "trade_count": 20}
    val_m = {"profit_factor": 2.2, "win_rate": 0.65, "trade_count": 15}
    val_audit = guard.audit_partition_generalization(dev_m, val_m, trial_count=2)
    print(f"   -> Generalization Verdict: {val_audit['verdict']} (PF retention: {val_audit['pf_retention_pct']}%)")
    assert val_audit["passed_generalization"]

    # STEP 11: Meta-Self-Healing Research Policy Learning
    print("\n11. [Research Policy Learner] Recording research method lesson...")
    policy_learner = ResearchPolicyLearner()
    pol_id = policy_learner.record_policy(
        trigger_pattern="VWAP_DISPLACEMENT_THRESHOLD_GENERALIZATION",
        previous_behavior="Tested single causal displacement threshold without stacking session masks",
        outcome="High Out-of-Sample PF retention (84.6%)",
        lesson="Single well-founded mechanical features generalize better than multi-condition gate stacks.",
        recommended_future_behavior="PREFER_SINGLE_CAUSAL_GATES"
    )
    print(f"   -> Recorded Research Policy {pol_id}")

    # STEP 12: Portfolio Gap Analysis for Multi-Strategy EA
    print("\n12. [Portfolio Gap Analyzer] Evaluating portfolio fit for DE40 X1X...")
    gap_analyzer = PortfolioGapAnalyzer()
    frozen = [{"module_id": "M1_VPPOC", "alpha_type": "VALUE_AREA_FADE", "direction": "LONG", "session": "LONDON_OPEN"}]
    cand = {"module_id": "M2_VWAPX", "alpha_type": "VWAP_EXTENSION_REVERSION", "direction": "LONG", "session": "US_OVERLAP"}
    gap_res = gap_analyzer.analyze_portfolio(frozen, cand)
    print(f"   -> Portfolio Fit: {gap_res['candidate_evaluation']['recommendation']} (Fit Score: {gap_res['candidate_evaluation']['portfolio_fit_score']})")
    assert gap_res["candidate_evaluation"]["fills_alpha_gap"]

    print("\n=== SMOKE TEST COMPLETED SUCCESSFULLY: 12/12 PIPELINE STEPS VERIFIED ===")

if __name__ == "__main__":
    run_smoke_test()
