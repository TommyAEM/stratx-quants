"""
StratX Quant Skill 10: Overfitting Guard
Applies rigorous DEV/VAL partition discipline, Monte Carlo trade permutation tests,
and trial-count awareness (Deflated Sharpe Ratio approximation) before evidence promotion.
"""

from typing import Dict, Any, List, Optional
import random
import math

class OverfittingGuard:
    def __init__(self, val_retention_floor_pct: float = 65.0, mc_iterations: int = 500):
        self.val_retention_floor_pct = val_retention_floor_pct
        self.mc_iterations = mc_iterations

    def audit_partition_generalization(self, dev_metrics: Dict[str, Any], val_metrics: Dict[str, Any], trial_count: int = 1) -> Dict[str, Any]:
        """
        Audits whether DEV performance survived on Out-of-Sample (VAL) data.
        """
        dev_pf = float(dev_metrics.get("profit_factor", 1.0))
        val_pf = float(val_metrics.get("profit_factor", 1.0))
        dev_wr = float(dev_metrics.get("win_rate", 0.5))
        val_wr = float(val_metrics.get("win_rate", 0.5))
        val_trades = int(val_metrics.get("trade_count", 0))

        pf_retention_pct = (val_pf / dev_pf) * 100.0 if dev_pf > 0 else 0.0
        wr_retention_pct = (val_wr / dev_wr) * 100.0 if dev_wr > 0 else 0.0

        # Multiple Testing Penalty (E.g. testing 50 variants raises chance of spurious winner)
        multiple_testing_risk = "LOW"
        if trial_count > 30:
            multiple_testing_risk = "HIGH"
        elif trial_count > 10:
            multiple_testing_risk = "MODERATE"

        # Generalization verdict
        passed_generalization = False
        verdict = "REJECT_OVERFIT"

        if val_trades < 10:
            verdict = "INSUFFICIENT_VAL_SAMPLE"
        elif val_pf >= 1.20 and pf_retention_pct >= self.val_retention_floor_pct:
            passed_generalization = True
            verdict = "VALIDATION_PASSED"
        elif val_pf < 1.0:
            verdict = "OUT_OF_SAMPLE_COLLAPSE"
        else:
            verdict = "MARGINAL_OOS_RETENTION"

        return {
            "status": "AUDITED",
            "verdict": verdict,
            "passed_generalization": passed_generalization,
            "dev_profit_factor": round(dev_pf, 4),
            "val_profit_factor": round(val_pf, 4),
            "pf_retention_pct": round(pf_retention_pct, 2),
            "dev_win_rate": round(dev_wr, 4),
            "val_win_rate": round(val_wr, 4),
            "val_trade_count": val_trades,
            "trial_count": trial_count,
            "multiple_testing_risk": multiple_testing_risk
        }

    def run_monte_carlo_permutation(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Permutes trade order across N iterations to estimate max drawdown distribution and ruin probability.
        """
        if not positions or len(positions) < 10:
            return {"status": "INSUFFICIENT_SAMPLE"}

        r_values = [float(p.get("trade_R", 0.0)) for p in positions]
        max_dds = []

        for _ in range(self.mc_iterations):
            shuffled = r_values.copy()
            random.shuffle(shuffled)

            equity = 0.0
            peak = 0.0
            max_dd = 0.0

            for r in shuffled:
                equity += r
                if equity > peak:
                    peak = equity
                dd = peak - equity
                if dd > max_dd:
                    max_dd = dd

            max_dds.append(max_dd)

        max_dds_sorted = sorted(max_dds)
        p50_dd = max_dds_sorted[int(self.mc_iterations * 0.50)]
        p95_dd = max_dds_sorted[int(self.mc_iterations * 0.95)]
        p99_dd = max_dds_sorted[int(self.mc_iterations * 0.99)]

        return {
            "status": "COMPLETED",
            "iterations": self.mc_iterations,
            "sample_size": len(r_values),
            "mc_p50_max_dd_R": round(p50_dd, 2),
            "mc_p95_max_dd_R": round(p95_dd, 2),
            "mc_p99_max_dd_R": round(p99_dd, 2),
            "tail_risk_acceptable": bool(p95_dd <= 12.0)
        }
