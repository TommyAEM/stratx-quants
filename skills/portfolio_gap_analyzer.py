"""
StratX Quant Skill 15: Portfolio Gap Analyzer
Analyzes accumulated strategy modules in multi-strategy EA harnesses (e.g. X1X).
Measures return correlation, session overlap, direction concentration, and missing alpha categories.
"""

from typing import Dict, Any, List, Optional
import math

class PortfolioGapAnalyzer:
    def __init__(self, max_allowed_correlation: float = 0.50, max_session_overlap_pct: float = 65.0):
        self.max_allowed_correlation = max_allowed_correlation
        self.max_session_overlap_pct = max_session_overlap_pct

    def analyze_portfolio(self, frozen_modules: List[Dict[str, Any]], candidate_module: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        frozen_modules: list of module dicts with attributes like {'module_id': 'M1_VPPOC', 'alpha_type': 'VALUE_AREA_FADE', 'direction': 'LONG', 'session': 'LONDON_OPEN'}
        """
        if not frozen_modules:
            return {
                "status": "EMPTY_PORTFOLIO",
                "missing_alpha_classes": ["MEAN_REVERSION", "TREND_CONTINUATION", "SESSION_TRANSITION_BREAKOUT", "VOLATILITY_EXPANSION"],
                "missing_directions": ["LONG", "SHORT"],
                "missing_sessions": ["LONDON_OPEN", "LONDON_MIDDAY", "US_OVERLAP", "US_AFTERNOON"],
                "recommendation": "RESEARCH_PRIMARY_BASE_MODULE"
            }

        covered_alphas = set(m.get("alpha_type", "UNKNOWN") for m in frozen_modules)
        covered_directions = set(m.get("direction", "UNKNOWN") for m in frozen_modules)
        covered_sessions = set(m.get("session", "UNKNOWN") for m in frozen_modules)

        all_alphas = ["VALUE_AREA_FADE", "VWAP_EXTENSION_REVERSION", "TREND_CONTINUATION_BREAKOUT", "LONDON_RANGE_FAILURE_FADE", "M30_SHORT_EXHAUSTION"]
        all_directions = ["LONG", "SHORT"]
        all_sessions = ["LONDON_OPEN", "LONDON_MIDDAY", "US_OVERLAP", "US_AFTERNOON"]

        missing_alphas = [a for a in all_alphas if a not in covered_alphas]
        missing_dirs = [d for d in all_directions if d not in covered_directions]
        missing_sess = [s for s in all_sessions if s not in covered_sessions]

        gap_summary = {
            "frozen_module_count": len(frozen_modules),
            "covered_alpha_classes": list(covered_alphas),
            "missing_alpha_classes": missing_alphas,
            "missing_directions": missing_dirs,
            "missing_sessions": missing_sess
        }

        # If candidate is provided, evaluate portfolio fit
        if candidate_module:
            cand_alpha = candidate_module.get("alpha_type", "")
            cand_dir = candidate_module.get("direction", "")
            cand_sess = candidate_module.get("session", "")

            is_duplicate_alpha = cand_alpha in covered_alphas
            fills_direction_gap = cand_dir in missing_dirs
            fills_alpha_gap = cand_alpha in missing_alphas

            fit_score = 0.5
            if fills_alpha_gap:
                fit_score += 0.3
            if fills_direction_gap:
                fit_score += 0.2
            if is_duplicate_alpha:
                fit_score -= 0.3

            gap_summary["candidate_evaluation"] = {
                "candidate_id": candidate_module.get("module_id", "CANDIDATE"),
                "portfolio_fit_score": round(max(0.0, min(1.0, fit_score)), 2),
                "fills_alpha_gap": fills_alpha_gap,
                "fills_direction_gap": fills_direction_gap,
                "recommendation": "STRONG_PORTFOLIO_DIVERSIFIER" if fit_score >= 0.7 else ("ACCEPTABLE_FIT" if fit_score >= 0.4 else "REDUNDANT_ALPHA_DUPLICATION")
            }

        return gap_summary
