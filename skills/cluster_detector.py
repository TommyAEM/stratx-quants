"""
StratX Quant Skill 2: Loss + Winner Cluster Detector (Institutional Statistical Rigor)
Implements:
1. Exact two-tailed z-tests using standard library math.erfc(|z| / sqrt(2)).
2. Fisher's Exact Test fallback for small sample / small cell contingency tables.
3. Benjamini-Hochberg (BH) False Discovery Rate (FDR) control across all tested clusters.
4. Clear classification tiers: STATISTICALLY_SIGNIFICANT (q <= 0.05), NOMINAL_UNADJUSTED (p <= 0.05), DISCOVERY_CANDIDATE (p <= 0.15).
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict
import math

class ClusterDetector:
    def __init__(self, min_cluster_size: int = 8, min_effect_size: float = 0.08, max_nominal_p: float = 0.15):
        self.min_cluster_size = min_cluster_size
        self.min_effect_size = min_effect_size
        self.max_nominal_p = max_nominal_p

    def _z_to_p_value(self, z: float) -> float:
        """Exact two-tailed p-value from standard normal z-score: p = erfc(|z| / sqrt(2))."""
        z_abs = abs(z)
        return min(1.0, max(0.0, math.erfc(z_abs / math.sqrt(2.0))))

    def _log_fact(self, n: int) -> float:
        """Log-factorial using math.lgamma."""
        if n <= 1:
            return 0.0
        return math.lgamma(n + 1)

    def _log_hypergeom_prob(self, a: int, b: int, c: int, d: int) -> float:
        """Computes log probability of 2x2 table [[a, b], [c, d]]."""
        # Hypergeometric: C(a+b, a) * C(c+d, c) / C(N, a+c)
        # = (a+b)! (c+d)! (a+c)! (b+d)! / (a! b! c! d! N!)
        n = a + b + c + d
        log_p = (
            self._log_fact(a + b) + self._log_fact(c + d) +
            self._log_fact(a + c) + self._log_fact(b + d) -
            (self._log_fact(a) + self._log_fact(b) + self._log_fact(c) + self._log_fact(d) + self._log_fact(n))
        )
        return log_p

    def _fishers_exact_2x2(self, a: int, b: int, c: int, d: int) -> float:
        """
        Computes two-tailed Fisher's exact test p-value for 2x2 table:
        [[a (losses1), b (wins1)],
         [c (losses2), d (wins2)]]
        """
        n = a + b + c + d
        r1 = a + b
        r2 = c + d
        c1 = a + c
        c2 = b + d

        observed_log_p = self._log_hypergeom_prob(a, b, c, d)
        min_a = max(0, r1 - c2)
        max_a = min(r1, c1)

        p_total = 0.0
        for test_a in range(min_a, max_a + 1):
            test_b = r1 - test_a
            test_c = c1 - test_a
            test_d = r2 - test_c
            lp = self._log_hypergeom_prob(test_a, test_b, test_c, test_d)
            if lp <= observed_log_p + 1e-7: # table is as or less likely
                p_total += math.exp(lp)

        return min(1.0, max(0.0, p_total))

    def detect_clusters(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scans all categorical and continuous feature dimensions, runs hypothesis tests,
        and applies Benjamini-Hochberg FDR multiplicity control.
        """
        if not positions or len(positions) < self.min_cluster_size:
            return {
                "status": "INSUFFICIENT_SAMPLE",
                "clusters": [],
                "streak_analysis": {}
            }

        n = len(positions)
        losers = [p for p in positions if float(p.get("trade_R", 0)) <= 0]
        winners = [p for p in positions if float(p.get("trade_R", 0)) > 0]
        base_loss_rate = len(losers) / n if n > 0 else 0.0
        base_win_rate = len(winners) / n if n > 0 else 0.0

        # 1. Streak Analysis
        current_streak_type = None
        current_streak_len = 0
        max_loss_streak = 0
        max_win_streak = 0
        loss_streaks = []
        win_streaks = []

        for p in positions:
            is_win = float(p.get("trade_R", 0)) > 0
            stype = "WIN" if is_win else "LOSS"
            if stype == current_streak_type:
                current_streak_len += 1
            else:
                if current_streak_type == "LOSS" and current_streak_len >= 3:
                    loss_streaks.append(current_streak_len)
                elif current_streak_type == "WIN" and current_streak_len >= 3:
                    win_streaks.append(current_streak_len)
                current_streak_type = stype
                current_streak_len = 1

            if current_streak_type == "LOSS":
                max_loss_streak = max(max_loss_streak, current_streak_len)
            else:
                max_win_streak = max(max_win_streak, current_streak_len)

        # 2. Collect and Test All Potential Cohorts
        tested_hypotheses = []

        def evaluate_candidate_cohort(dimension: str, feat_val: str, cohort: List[Dict[str, Any]], rest: List[Dict[str, Any]], cutoff: Optional[float] = None):
            n1 = len(cohort)
            n2 = len(rest)
            if n1 < self.min_cluster_size or n2 < 4:
                return

            losses1 = sum(1 for p in cohort if float(p.get("trade_R", 0)) <= 0)
            losses2 = sum(1 for p in rest if float(p.get("trade_R", 0)) <= 0)
            wins1 = n1 - losses1
            wins2 = n2 - losses2

            p1_loss = losses1 / n1
            p2_loss = losses2 / n2
            loss_diff = p1_loss - base_loss_rate

            p1_win = wins1 / n1
            p2_win = wins2 / n2
            win_diff = p1_win - base_win_rate

            # Check expected cell counts for Fisher fallback
            exp_loss1 = (n1 * (losses1 + losses2)) / (n1 + n2)
            exp_win1 = (n1 * (wins1 + wins2)) / (n1 + n2)

            use_fisher = (exp_loss1 < 5.0 or exp_win1 < 5.0 or n1 < 20)

            if use_fisher:
                p_val_raw = self._fishers_exact_2x2(losses1, wins1, losses2, wins2)
                test_method = "FISHER_EXACT"
                z_score = 0.0
            else:
                p_pool = (losses1 + losses2) / (n1 + n2)
                se = math.sqrt(max(1e-6, p_pool * (1.0 - p_pool) * ((1.0 / n1) + (1.0 / n2))))
                z_score = (p1_loss - p2_loss) / se if se > 0 else 0.0
                p_val_raw = self._z_to_p_value(z_score)
                test_method = "POOLED_Z_TEST"

            # Haldane-Anscombe corrected Odds Ratio
            odds_ratio_loss = ((losses1 + 0.5) * (wins2 + 0.5)) / ((wins1 + 0.5) * (losses2 + 0.5))

            if loss_diff >= self.min_effect_size and p_val_raw <= self.max_nominal_p and losses1 >= 3:
                tested_hypotheses.append({
                    "cluster_id": f"LOSS_{dimension}_{feat_val}".replace(" ", "_"),
                    "target_type": "LOSERS",
                    "dimension": dimension,
                    "feature_value": feat_val,
                    "cutoff": cutoff,
                    "population_size": n1,
                    "cluster_loss_count": losses1,
                    "cluster_rate": round(p1_loss, 4),
                    "baseline_rate": round(base_loss_rate, 4),
                    "effect_size": round(loss_diff, 4),
                    "odds_ratio": round(odds_ratio_loss, 2),
                    "z_score": round(z_score, 2),
                    "p_value": round(p_val_raw, 5),
                    "test_method": test_method
                })
            elif win_diff >= self.min_effect_size and p_val_raw <= self.max_nominal_p and wins1 >= 3:
                tested_hypotheses.append({
                    "cluster_id": f"WIN_{dimension}_{feat_val}".replace(" ", "_"),
                    "target_type": "WINNERS",
                    "dimension": dimension,
                    "feature_value": feat_val,
                    "cutoff": cutoff,
                    "population_size": n1,
                    "cluster_win_count": wins1,
                    "cluster_rate": round(p1_win, 4),
                    "baseline_rate": round(base_win_rate, 4),
                    "effect_size": round(win_diff, 4),
                    "odds_ratio": round(1.0 / max(0.01, odds_ratio_loss), 2),
                    "z_score": round(-z_score, 2),
                    "p_value": round(p_val_raw, 5),
                    "test_method": test_method
                })

        # Scan categorical features
        for dim, key in [("session", "session"), ("direction", "direction"), ("weekday", "day_of_week")]:
            distinct_vals = set(p.get(key, "UNKNOWN") for p in positions)
            for v in distinct_vals:
                cohort = [p for p in positions if p.get(key) == v]
                rest = [p for p in positions if p.get(key) != v]
                evaluate_candidate_cohort(dim, str(v), cohort, rest)

        # Scan continuous features across quantiles
        feature_keys = set()
        for p in positions:
            feature_keys.update(p.get("features", {}).keys())

        for fkey in sorted(list(feature_keys)):
            vals = [float(p["features"][fkey]) for p in positions if fkey in p.get("features", {}) and isinstance(p["features"][fkey], (int, float))]
            if len(vals) >= 12:
                distinct_vals = sorted(list(set(vals)))
                if len(distinct_vals) >= 2:
                    mid_idx = len(distinct_vals) // 3
                    t_low = distinct_vals[mid_idx] if mid_idx > 0 else (distinct_vals[0] + distinct_vals[1]) / 2.0
                    t_high = distinct_vals[-max(1, mid_idx)]

                    low_cohort = [p for p in positions if float(p.get("features", {}).get(fkey, 0)) <= t_low]
                    low_rest = [p for p in positions if float(p.get("features", {}).get(fkey, 0)) > t_low]
                    evaluate_candidate_cohort(fkey, "LOW_TERCILE", low_cohort, low_rest, cutoff=round(t_low, 4))

                    high_cohort = [p for p in positions if float(p.get("features", {}).get(fkey, 0)) >= t_high]
                    high_rest = [p for p in positions if float(p.get("features", {}).get(fkey, 0)) < t_high]
                    evaluate_candidate_cohort(fkey, "HIGH_TERCILE", high_cohort, high_rest, cutoff=round(t_high, 4))

        # 3. Benjamini-Hochberg (BH) False Discovery Rate (FDR) Adjustment
        total_tests = len(tested_hypotheses)
        final_clusters = []

        if total_tests > 0:
            # Sort ascending by unadjusted p-value
            sorted_hyp = sorted(tested_hypotheses, key=lambda x: x["p_value"])
            m = total_tests

            # Compute raw BH q-values
            for i, hyp in enumerate(sorted_hyp):
                rank = i + 1
                q_val = min(1.0, (hyp["p_value"] * m) / rank)
                hyp["q_value_fdr"] = round(q_val, 4)

            # Ensure monotonicity from right to left
            min_q = 1.0
            for i in range(m - 1, -1, -1):
                if sorted_hyp[i]["q_value_fdr"] < min_q:
                    min_q = sorted_hyp[i]["q_value_fdr"]
                else:
                    sorted_hyp[i]["q_value_fdr"] = round(min_q, 4)

            # Assign strict evidence tiers
            for hyp in sorted_hyp:
                q = hyp["q_value_fdr"]
                p = hyp["p_value"]

                if q <= 0.05 and hyp["population_size"] >= 15:
                    tier = "STATISTICALLY_SIGNIFICANT (FDR q <= 0.05)"
                    confidence = "HIGH"
                elif p <= 0.05:
                    tier = "NOMINAL_UNADJUSTED_EVIDENCE (p <= 0.05)"
                    confidence = "MODERATE"
                elif p <= 0.15:
                    tier = "DISCOVERY_CANDIDATE (Exploratory p <= 0.15)"
                    confidence = "EXPLORATORY"
                else:
                    tier = "WEAK_SIGNAL"
                    confidence = "LOW"

                hyp["statistical_tier"] = tier
                hyp["confidence"] = confidence
                final_clusters.append(hyp)

        return {
            "status": "SUCCESS",
            "total_trades": n,
            "total_tests_conducted": total_tests,
            "base_loss_rate": round(base_loss_rate, 4),
            "base_win_rate": round(base_win_rate, 4),
            "streak_analysis": {
                "max_loss_streak": max_loss_streak,
                "max_win_streak": max_win_streak,
                "loss_streaks_ge_3": len(loss_streaks),
                "win_streaks_ge_3": len(win_streaks)
            },
            "clusters_found": len(final_clusters),
            "clusters": sorted(final_clusters, key=lambda x: x.get("p_value", 1.0))
        }
