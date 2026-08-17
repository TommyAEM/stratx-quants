#!/usr/bin/env python3
"""
StratX Quant Skills — Complete Unified Command-Line Interface
Exposes all 16 quantitative scientific skills to DeepSeek agents and bash tools.
"""

import sys
import json
import csv
import argparse
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

def load_data(path_str: str):
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path_str}")
    if p.suffix.lower() == ".csv":
        with open(p, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    elif p.suffix.lower() == ".json":
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            with open(p, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))

def main():
    parser = argparse.ArgumentParser(description="StratX Complete Quant Skills CLI")
    subparsers = parser.add_subparsers(dest="command", help="Skill command to execute")

    # 1. trade_population
    p_pop = subparsers.add_parser("trade_population", help="Analyze and reconcile trade population")
    p_pop.add_argument("--input", required=True, help="Path to CSV or JSON trade records")

    # 2. detect_clusters
    p_clust = subparsers.add_parser("detect_clusters", help="Detect losing/winning clusters")
    p_clust.add_argument("--input", required=True, help="Path to CSV or JSON positions")

    # 3. tag_regimes
    p_tag = subparsers.add_parser("tag_regimes", help="Tag point-in-time market regimes")
    p_tag.add_argument("--input", required=True, help="Path to CSV or JSON positions")

    # 4. causal_decompose
    p_causal = subparsers.add_parser("causal_decompose", help="Run causal decomposition on a feature/factor")
    p_causal.add_argument("--input", required=True, help="Path to CSV or JSON positions")
    p_causal.add_argument("--factor", required=True, help="Feature name (e.g. f_disp, f_rel_vol)")
    p_causal.add_argument("--threshold", type=float, default=1.0, help="Cutoff threshold for exposure")

    # 5. classify_failure
    p_fail = subparsers.add_parser("classify_failure", help="Classify strategy failure taxonomy")
    p_fail.add_argument("--evidence", required=True, help="Path to JSON evidence file or raw JSON string")

    # 6. child_parent_delta
    p_delta = subparsers.add_parser("child_parent_delta", help="Compute trade delta between parent and child")
    p_delta.add_argument("--parent", required=True, help="Path to Parent CSV/JSON")
    p_delta.add_argument("--child", required=True, help="Path to Child CSV/JSON")

    # 7. validate_experiment
    p_val_exp = subparsers.add_parser("validate_experiment", help="Validate Experiment Spec vs Receipt")
    p_val_exp.add_argument("--spec", required=True, help="Path to Spec JSON")
    p_val_exp.add_argument("--receipt", required=True, help="Path to Receipt JSON")

    # 8. self_review_create_goal
    p_sg = subparsers.add_parser("self_review_create_goal", help="Initialize a persistent Goal-Based Self-Review session")
    p_sg.add_argument("--mission", default="de40-x1x", help="Mission ID")
    p_sg.add_argument("--module", default="M1_VPPOC", help="Module ID")
    p_sg.add_argument("--parent", required=True, help="Parent Candidate ID")
    p_sg.add_argument("--goal_id", required=True, help="Goal ID")
    p_sg.add_argument("--definition", required=True, help="Goal description")
    p_sg.add_argument("--metrics", required=True, help="JSON string or file of target metrics")
    p_sg.add_argument("--constraints", default="{}", help="JSON string or file of constraints")

    # 9. self_review_evaluate_goal
    p_se = subparsers.add_parser("self_review_evaluate_goal", help="Evaluate current candidate against persistent goal")
    p_se.add_argument("--session", required=True, help="Path to Self-Review Session JSON")
    p_se.add_argument("--candidate", required=True, help="Candidate ID")
    p_se.add_argument("--metrics", required=True, help="Path to Candidate Metrics JSON")
    p_se.add_argument("--delta", required=True, help="Path to Child-Parent Delta JSON")
    p_se.add_argument("--spec", default=None, help="Path to Experiment Spec JSON (optional)")
    p_se.add_argument("--receipt", default=None, help="Path to Receipt JSON (optional)")

    # 10. can_exit_self_review
    p_ce = subparsers.add_parser("can_exit_self_review", help="Deterministic check if Self-Review may exit to Reviewer")
    p_ce.add_argument("--session", required=True, help="Path to Self-Review Session JSON")

    # 11. self_review (14-point review record generator)
    p_srev = subparsers.add_parser("self_review", help="Execute mandatory Self-Review loop on child outcome")
    p_srev.add_argument("--mission", default="de40-x1x", help="Mission ID")
    p_srev.add_argument("--generation", default="GEN_1", help="Generation ID")
    p_srev.add_argument("--spec", required=True, help="Path to Experiment Spec JSON")
    p_srev.add_argument("--delta", required=True, help="Path to Child-Parent Delta JSON")
    p_srev.add_argument("--receipt", default=None, help="Path to Implementation Receipt JSON (optional)")

    # 12. validate_workflow_gates
    p_vgate = subparsers.add_parser("validate_workflow_gates", help="Validate that Self-Review and Re-Forensics gates pass")
    p_vgate.add_argument("--self_review", required=True, help="Path to Self Review Record JSON")
    p_vgate.add_argument("--child_reforensics", default=None, help="Path to Child Re-Forensics JSON")

    # 13. explore_landscape
    p_land = subparsers.add_parser("explore_landscape", help="Analyze parameter landscape plateaus")
    p_land.add_argument("--param", required=True, help="Parameter name")
    p_land.add_argument("--grid", required=True, help="Path to Grid results JSON")

    # 14. audit_overfit
    p_over = subparsers.add_parser("audit_overfit", help="Audit DEV/VAL generalization and Monte Carlo")
    p_over.add_argument("--dev", required=True, help="Path to DEV metrics JSON")
    p_over.add_argument("--val", required=True, help="Path to VAL metrics JSON")
    p_over.add_argument("--trials", type=int, default=1, help="Trial count")

    # 15. evaluate_action
    p_pol = subparsers.add_parser("evaluate_action", help="Evaluate planned action against meta-research policies")
    p_pol.add_argument("--context", required=True, help="Path to Action Context JSON")

    # 16. rank_eiv
    p_eiv = subparsers.add_parser("rank_eiv", help="Rank research candidates by Expected Information Value")
    p_eiv.add_argument("--candidates", required=True, help="Path to candidates JSON")

    # 17. evaluate_exhaustion
    p_exh = subparsers.add_parser("evaluate_exhaustion", help="Evaluate family exhaustion evidence")
    p_exh.add_argument("--family", required=True, help="Family name")
    p_exh.add_argument("--evidence", required=True, help="Path to family evidence JSON")

    # 18. portfolio_gap
    p_gap = subparsers.add_parser("portfolio_gap", help="Analyze portfolio gaps across frozen modules")
    p_gap.add_argument("--modules", required=True, help="Path to JSON file with frozen modules")
    p_gap.add_argument("--candidate", default=None, help="Path to candidate module JSON (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "trade_population":
            raw = load_data(args.input)
            analyzer = TradePopulationAnalyzer()
            res = analyzer.analyze_trades(raw)
            print(json.dumps(res, indent=2))

        elif args.command == "detect_clusters":
            raw = load_data(args.input)
            analyzer = TradePopulationAnalyzer()
            pop = analyzer.analyze_trades(raw)["positions"]
            detector = ClusterDetector()
            res = detector.detect_clusters(pop)
            print(json.dumps(res, indent=2))

        elif args.command == "tag_regimes":
            raw = load_data(args.input)
            analyzer = TradePopulationAnalyzer()
            pop = analyzer.analyze_trades(raw)["positions"]
            tagger = RegimeTagger()
            res = tagger.tag_population(pop)
            print(json.dumps(res, indent=2))

        elif args.command == "causal_decompose":
            raw = load_data(args.input)
            analyzer = TradePopulationAnalyzer()
            pop = analyzer.analyze_trades(raw)["positions"]
            decomposer = CausalDecomposer()
            thresh = args.threshold
            factor_k = args.factor
            res = decomposer.decompose_factor(pop, factor_k, lambda p: float(p.get("features", {}).get(factor_k, 0)) < thresh)
            print(json.dumps(res, indent=2))

        elif args.command == "classify_failure":
            try:
                ev = json.loads(args.evidence)
            except Exception:
                ev = load_data(args.evidence)
            classifier = FailureModeClassifier()
            res = classifier.classify_failure(ev)
            print(json.dumps(res, indent=2))

        elif args.command == "child_parent_delta":
            p_raw = load_data(args.parent)
            c_raw = load_data(args.child)
            analyzer = TradePopulationAnalyzer()
            p_pop = analyzer.analyze_trades(p_raw)["positions"]
            c_pop = analyzer.analyze_trades(c_raw)["positions"]
            delta_eng = ChildParentDelta()
            res = delta_eng.compute_delta(p_pop, c_pop)
            print(json.dumps(res, indent=2))

        elif args.command == "validate_experiment":
            spec = load_data(args.spec)
            receipt = load_data(args.receipt)
            mut_engine = StructuralMutationEngine()
            res = mut_engine.validate_implementation(spec, receipt)
            print(json.dumps(res, indent=2))

        elif args.command == "self_review_create_goal":
            try:
                metrics = json.loads(args.metrics)
            except Exception:
                metrics = load_data(args.metrics)
            try:
                constraints = json.loads(args.constraints)
            except Exception:
                constraints = load_data(args.constraints)
            engine = SelfReviewEngine()
            session = engine.create_goal_session(
                mission_id=args.mission,
                module_id=args.module,
                parent_id=args.parent,
                goal_id=args.goal_id,
                goal_definition=args.definition,
                goal_metrics=metrics,
                goal_constraints=constraints
            )
            print(json.dumps(session, indent=2))

        elif args.command == "self_review_evaluate_goal":
            session = load_data(args.session)
            metrics = load_data(args.metrics)
            delta = load_data(args.delta)
            spec = load_data(args.spec) if args.spec else None
            receipt = load_data(args.receipt) if args.receipt else None
            engine = SelfReviewEngine()
            res = engine.evaluate_goal(session, args.candidate, metrics, delta, spec=spec, receipt=receipt)
            print(json.dumps(res, indent=2))

        elif args.command == "can_exit_self_review":
            session = load_data(args.session)
            engine = SelfReviewEngine()
            res = engine.can_exit_self_review(session)
            print(json.dumps(res, indent=2))

        elif args.command == "self_review":
            spec = load_data(args.spec)
            delta = load_data(args.delta)
            receipt = load_data(args.receipt) if args.receipt else None
            engine = SelfReviewEngine()
            record = engine.create_self_review(
                mission_id=args.mission,
                generation_id=args.generation,
                experiment_id=spec.get("experiment_id", "EXP_01"),
                parent_id=spec.get("parent_strategy_id", "PARENT"),
                child_id=f"{spec.get('experiment_id', 'EXP_01')}_CHILD",
                experiment_spec=spec,
                child_parent_delta=delta,
                child_metrics={},
                implementation_receipt=receipt
            )
            print(json.dumps(record, indent=2))

        elif args.command == "validate_workflow_gates":
            srev = load_data(args.self_review)
            reforens = load_data(args.child_reforensics) if args.child_reforensics else None
            engine = SelfReviewEngine()
            gate_res = engine.validate_workflow_gates({}, srev, reforens)
            print(json.dumps(gate_res, indent=2))

        elif args.command == "explore_landscape":
            grid = load_data(args.grid)
            param_explorer = ParameterLandscapeExplorer()
            res = param_explorer.analyze_surface(args.param, grid)
            print(json.dumps(res, indent=2))

        elif args.command == "audit_overfit":
            dev = load_data(args.dev)
            val = load_data(args.val)
            guard = OverfittingGuard()
            res = guard.audit_partition_generalization(dev, val, trial_count=args.trials)
            print(json.dumps(res, indent=2))

        elif args.command == "evaluate_action":
            ctx = load_data(args.context)
            learner = ResearchPolicyLearner()
            res = learner.evaluate_research_action(ctx)
            print(json.dumps(res, indent=2))

        elif args.command == "rank_eiv":
            cands = load_data(args.candidates)
            engine = ResearchMapEIVEngine()
            res = engine.rank_candidates(cands)
            print(json.dumps(res, indent=2))

        elif args.command == "evaluate_exhaustion":
            ev = load_data(args.evidence)
            engine = ResearchExhaustionEngine()
            res = engine.evaluate_family_exhaustion(args.family, ev)
            print(json.dumps(res, indent=2))

        elif args.command == "portfolio_gap":
            mods = load_data(args.modules)
            cand = load_data(args.candidate) if args.candidate else None
            gap_eng = PortfolioGapAnalyzer()
            res = gap_eng.analyze_portfolio(mods, cand)
            print(json.dumps(res, indent=2))

    except Exception as e:
        print(json.dumps({"status": "ERROR", "error_message": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
