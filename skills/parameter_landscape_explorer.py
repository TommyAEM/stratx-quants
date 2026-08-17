"""
StratX Quant Skill 9: Parameter Landscape Explorer
Maps parameter sensitivity surfaces, identifies broad stable plateaus vs fragile knife-edge peaks,
and rejects overfit solutions that collapse under slight neighborhood shifts.
"""

from typing import Dict, Any, List, Optional
import math

class ParameterLandscapeExplorer:
    def __init__(self, plateau_breadth_threshold_pct: float = 20.0, drop_tolerance_pct: float = 25.0):
        self.plateau_breadth_threshold_pct = plateau_breadth_threshold_pct
        self.drop_tolerance_pct = drop_tolerance_pct

    def analyze_surface(self, parameter_name: str, grid_results: List[Dict[str, Any]], primary_metric: str = "profit_factor") -> Dict[str, Any]:
        """
        grid_results: list of dicts like {'param_val': 1.5, 'profit_factor': 2.1, 'trade_count': 45}
        """
        if not grid_results or len(grid_results) < 3:
            return {
                "parameter_name": parameter_name,
                "status": "INSUFFICIENT_TRIALS",
                "classification": "UNKNOWN"
            }

        sorted_grid = sorted(grid_results, key=lambda x: float(x.get("param_val", 0)))
        vals = [float(x.get("param_val", 0)) for x in sorted_grid]
        scores = [float(x.get(primary_metric, 0)) for x in sorted_grid]

        best_idx = scores.index(max(scores))
        best_val = vals[best_idx]
        best_score = scores[best_idx]

        # Calculate neighbors degradation
        left_score = scores[best_idx - 1] if best_idx > 0 else best_score
        right_score = scores[best_idx + 1] if best_idx < len(scores) - 1 else best_score

        left_drop_pct = ((best_score - left_score) / best_score) * 100.0 if best_score > 0 else 0.0
        right_drop_pct = ((best_score - right_score) / best_score) * 100.0 if best_score > 0 else 0.0
        avg_neighbor_drop = (left_drop_pct + right_drop_pct) / 2.0

        # Plateau check: count how many contiguous points remain within drop_tolerance_pct
        plateau_points = []
        for i, s in enumerate(scores):
            if s >= best_score * (1.0 - (self.drop_tolerance_pct / 100.0)):
                plateau_points.append(vals[i])

        plateau_span = max(plateau_points) - min(plateau_points) if plateau_points else 0.0
        val_range = max(vals) - min(vals) if max(vals) > min(vals) else 1.0
        span_pct = (plateau_span / val_range) * 100.0

        classification = "FRAGILE_SPIKE"
        is_robust = False

        if span_pct >= self.plateau_breadth_threshold_pct and avg_neighbor_drop <= self.drop_tolerance_pct:
            classification = "BROAD_STABLE_PLATEAU"
            is_robust = True
        elif avg_neighbor_drop > 45.0:
            classification = "DANGEROUS_KNIFE_EDGE"
            is_robust = False
        else:
            classification = "MODERATE_PLATEAU"
            is_robust = True

        return {
            "parameter_name": parameter_name,
            "status": "ANALYZED",
            "best_value": best_val,
            "best_score": round(best_score, 4),
            "classification": classification,
            "is_robust_plateau": is_robust,
            "average_neighbor_drop_pct": round(avg_neighbor_drop, 2),
            "plateau_span_pct_of_range": round(span_pct, 2),
            "stable_region": [min(plateau_points), max(plateau_points)] if plateau_points else [best_val, best_val],
            "recommendation": "ACCEPT_REGION" if is_robust else "REJECT_OVERFIT_SPIKE"
        }
