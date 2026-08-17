"""
StratX Quant Skill 4: Causal Decomposition Engine
Compares failure cohorts against MATCHED WINNER cohorts to separate genuine causal mechanisms
from spurious correlations. Computes odds ratio, risk ratio, effect sizes, and confounder checks.
"""

from typing import Dict, Any, List, Optional
import math

class CausalDecomposer:
    def __init__(self, min_matched_sample: int = 4):
        self.min_matched_sample = min_matched_sample

    def decompose_factor(self, positions: List[Dict[str, Any]], factor_name: str, factor_eval_fn) -> Dict[str, Any]:
        """
        Evaluates a candidate factor against the entire population, comparing exposed vs unexposed cohorts.
        factor_eval_fn(pos) -> True if factor is present (e.g. pos['features']['f_disp'] < 1.0)
        """
        if not positions or len(positions) < self.min_matched_sample:
            return {
                "factor_name": factor_name,
                "status": "INSUFFICIENT_SAMPLE",
                "causal_confidence": "NONE"
            }

        exposed_wins = 0
        exposed_losses = 0
        unexposed_wins = 0
        unexposed_losses = 0

        exposed_r = []
        unexposed_r = []

        for p in positions:
            is_win = p.get("trade_R", 0) > 0
            r_val = float(p.get("trade_R", 0))
            is_exposed = bool(factor_eval_fn(p))

            if is_exposed:
                exposed_r.append(r_val)
                if is_win:
                    exposed_wins += 1
                else:
                    exposed_losses += 1
            else:
                unexposed_r.append(r_val)
                if is_win:
                    unexposed_wins += 1
                else:
                    unexposed_losses += 1

        n_exp = exposed_wins + exposed_losses
        n_unexp = unexposed_wins + unexposed_losses

        if n_exp == 0 or n_unexp == 0:
            return {
                "factor_name": factor_name,
                "status": "ZERO_VARIANCE_COHORT",
                "causal_confidence": "NONE"
            }

        exp_wr = exposed_wins / n_exp if n_exp > 0 else 0.0
        unexp_wr = unexposed_wins / n_unexp if n_unexp > 0 else 0.0

        exp_exp_r = sum(exposed_r) / n_exp if n_exp > 0 else 0.0
        unexp_exp_r = sum(unexposed_r) / n_unexp if n_unexp > 0 else 0.0

        # Odds Ratio for Loss: (exposed_loss / exposed_win) / (unexposed_loss / unexposed_win)
        a = exposed_losses + 0.5
        b = exposed_wins + 0.5
        c = unexposed_losses + 0.5
        d = unexposed_wins + 0.5
        odds_ratio = (a * d) / (b * c)
        log_or = math.log(odds_ratio)
        se_log_or = math.sqrt((1.0/a) + (1.0/b) + (1.0/c) + (1.0/d))

        # Risk Ratio (Relative Risk of Loss)
        p_loss_exp = (exposed_losses + 0.5) / (n_exp + 1.0)
        p_loss_unexp = (unexposed_losses + 0.5) / (n_unexp + 1.0)
        relative_risk = p_loss_exp / p_loss_unexp

        # Effect size (Cohen's d on trade_R)
        mean_diff = exp_exp_r - unexp_exp_r
        var_exp = sum((x - exp_exp_r)**2 for x in exposed_r) / max(1, n_exp - 1)
        var_unexp = sum((x - unexp_exp_r)**2 for x in unexposed_r) / max(1, n_unexp - 1)
        pooled_sd = math.sqrt(max(0.001, (var_exp + var_unexp) / 2.0))
        cohens_d = mean_diff / pooled_sd if pooled_sd > 0 else 0.0

        # Causal confidence evaluation
        causal_conf = "LOW"
        support_strength = "WEAK"

        if odds_ratio > 2.0:
            if n_exp >= 10 and n_unexp >= 10 and abs(log_or / se_log_or) >= 1.96:
                causal_conf = "HIGH"
                support_strength = "STRONG"
            elif n_exp >= 3 and n_unexp >= 3:
                causal_conf = "MODERATE"
                support_strength = "MODERATE"

        # Confounder audit: check if direction or session explains the difference
        confounders = []
        exp_long_pct = sum(1 for p in positions if factor_eval_fn(p) and p.get("direction") == "LONG") / max(1, n_exp)
        unexp_long_pct = sum(1 for p in positions if not factor_eval_fn(p) and p.get("direction") == "LONG") / max(1, n_unexp)
        if abs(exp_long_pct - unexp_long_pct) > 0.40:
            confounders.append("DIRECTION_ASYMMETRY (Cohort is heavily skewed towards one trade direction)")

        exp_ldn_pct = sum(1 for p in positions if factor_eval_fn(p) and "LONDON" in str(p.get("session", ""))) / max(1, n_exp)
        unexp_ldn_pct = sum(1 for p in positions if not factor_eval_fn(p) and "LONDON" in str(p.get("session", ""))) / max(1, n_unexp)
        if abs(exp_ldn_pct - unexp_ldn_pct) > 0.40:
            confounders.append("SESSION_CONFOUNDER (Factor is confounded by London vs US session timing)")

        return {
            "factor_name": factor_name,
            "status": "ANALYZED",
            "exposed_count": n_exp,
            "unexposed_count": n_unexp,
            "exposed_win_rate": round(exp_wr, 4),
            "unexposed_win_rate": round(unexp_wr, 4),
            "exposed_expectancy_R": round(exp_exp_r, 4),
            "unexposed_expectancy_R": round(unexp_exp_r, 4),
            "odds_ratio_loss": round(odds_ratio, 4),
            "relative_risk_loss": round(relative_risk, 4),
            "cohens_d_effect_size": round(cohens_d, 4),
            "support_strength": support_strength,
            "causal_confidence": causal_conf,
            "suspected_confounders": confounders,
            "recommendation": "PROCEED_TO_BRANCH_EXPERIMENT" if (causal_conf in ["HIGH", "MODERATE"] and not confounders) else "REJECT_OR_ISOLATE_CONFOUNDER"
        }
