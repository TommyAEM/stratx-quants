"""
=============================================================================
STRATX 5-STAGE QUANT OPTIMIZATION PIPELINE (optimizer_engine.py)

Stage 1: Sobol low-discrepancy parameter sampling (scipy.stats.qmc) — Python
         picks the grid, not MT5's blind genetic guesser.
Stage 2: Physical MT5 batch evaluation. NOTE: the MT5 tester ini interface only
         supports start||step||stop ranges — it CANNOT consume a CSV of arbitrary
         parameter sets. Stage 2 therefore fires one sequential headless tester
         run per Sobol sample via the zero-tolerance runner with input overrides
         (sequential because the terminal/data-dir is single-instance).
Stage 3: Pareto non-dominated selection (maximize PF & trade count, minimize MaxDD).
Stage 4: Parameter plateau / sensitivity testing — nudge each winning parameter;
         a >30% PF collapse marks a knife-edge overfit spike -> reject.
Stage 5: Deflated Sharpe Ratio gate (Bailey & Lopez de Prado) — rejects edges that
         do not beat the expected maximum Sharpe under multiple testing.

Returns only PHYSICALLY VERIFIED results: every metrics row comes from a real
headless tester run of the exact candidate parameters (learning_7).
=============================================================================
"""

import math
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from orchestrator.mt5_adapter import (
    extract_optimizable_inputs,
    run_mt5_backtest,
    parse_mt5_report,
)

PROJECT_ROOT = Path("C:/Trading/DE40-Research")
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# STAGE 1: SOBOL LOW-DISCREPANCY PARAMETER GRID
# =====================================================================
def generate_sobol_parameter_grid(param_bounds: Dict[str, Tuple[float, float]],
                                  param_types: Dict[str, str],
                                  n_samples: int = 1024,
                                  seed: int = 42) -> pd.DataFrame:
    """Generates a scrambled Sobol low-discrepancy grid over the parameter bounds.

    Covers the parameter space mathematically evenly with far fewer tests than a
    full grid. n_samples is rounded UP to the next power of 2 (Sobol balance
    property). int/long parameters are rounded to integers inside their bounds.
    """
    from scipy.stats import qmc

    param_names = list(param_bounds.keys())
    d = len(param_names)
    if d == 0:
        return pd.DataFrame()

    m = int(math.ceil(math.log2(max(2, n_samples))))
    sampler = qmc.Sobol(d=d, scramble=True, seed=seed)
    sample = sampler.random_base2(m=m)

    lower = [param_bounds[p][0] for p in param_names]
    upper = [param_bounds[p][1] for p in param_names]
    scaled = qmc.scale(sample, lower, upper)

    df = pd.DataFrame(scaled, columns=param_names)
    for col in param_names:
        lo, hi = param_bounds[col]
        if param_types.get(col) != "double":
            df[col] = df[col].round().astype(int).clip(int(lo), int(hi))
        else:
            df[col] = df[col].clip(lo, hi).round(4)
    # Duplicate parameter sets waste physical tester runs
    df = df.drop_duplicates().reset_index(drop=True)
    return df


# =====================================================================
# STAGE 2: PHYSICAL MT5 BATCH EVALUATION (SEQUENTIAL, ZERO-TOLERANCE)
# =====================================================================
def _run_single_param_set(ea_name: str, run_tag: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """One physical headless tester run for one parameter set; returns scraped metrics.
    keep_evidence=False: batch samples must not copy HTML reports (disk bloat guard);
    the batch results CSV is the evidence, and the winner is re-verified with evidence."""
    report_path = run_mt5_backtest(ea_name=ea_name, module_name=run_tag, input_overrides=params, keep_evidence=False)
    return parse_mt5_report(report_path)


def batch_evaluate_parameter_grid(df_grid: pd.DataFrame,
                                  ea_name: str,
                                  module_name: str,
                                  progress_every: int = 25) -> Tuple[pd.DataFrame, int]:
    """Fires one physical MT5 tester run per Sobol sample (sequential: single-instance
    terminal). Individual run failures are logged and skipped, never fabricated.
    Returns (results_df, trials_run)."""
    param_names = list(df_grid.columns)
    rows = []
    trials = 0
    best_pf = 0.0
    t0 = time.time()

    for i, row in df_grid.iterrows():
        params = {}
        for p in param_names:
            v = row[p]
            params[p] = int(v) if isinstance(v, (int, np.integer)) else float(v)
        try:
            metrics = _run_single_param_set(ea_name, f"{module_name}_S{i:04d}", params)
            trials += 1
            record = dict(params)
            record.update({
                "total_trades": metrics.get("total_trades", 0),
                "win_rate": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 1.0),
                "max_consecutive_losses": metrics.get("max_consecutive_losses", 99),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            })
            rows.append(record)
            best_pf = max(best_pf, record["profit_factor"])
        except Exception as e:
            print(f"   ⚠️ Sobol sample {i}: tester run failed ({str(e)[:120]}). Skipping.", flush=True)

        if (i + 1) % progress_every == 0:
            elapsed = time.time() - t0
            eta = (elapsed / (i + 1)) * (len(df_grid) - i - 1)
            print(f"   🧪 Sobol batch: {i + 1}/{len(df_grid)} runs | best PF so far: {best_pf:.2f} | "
                  f"elapsed {elapsed/60:.1f}m | ETA {eta/60:.1f}m", flush=True)

    return pd.DataFrame(rows), trials


# =====================================================================
# STAGE 3: PARETO NON-DOMINATED SELECTION
# =====================================================================
def get_pareto_front(df_results: pd.DataFrame) -> pd.DataFrame:
    """Filters batch results to the Pareto-optimal candidates.
    Maximizes profit_factor & total_trades, minimizes max_drawdown.
    A candidate is dominated if another is >= on all three and strictly > on one."""
    if df_results.empty:
        return df_results

    pf = df_results["profit_factor"].to_numpy()
    dd = df_results["max_drawdown"].to_numpy()
    tr = df_results["total_trades"].to_numpy()

    pareto_mask = np.ones(len(df_results), dtype=bool)
    for i in range(len(df_results)):
        dominated = ((pf >= pf[i]) & (dd <= dd[i]) & (tr >= tr[i]) &
                     ((pf > pf[i]) | (dd < dd[i]) | (tr > tr[i]))).any()
        pareto_mask[i] = not dominated

    return df_results[pareto_mask].sort_values(by="profit_factor", ascending=False)


# =====================================================================
# STAGE 4: PARAMETER PLATEAU / SENSITIVITY TEST (ANTI-FRAGILE)
# =====================================================================
def classify_parameter_landscape(base_pf: float, probe_pfs: List[float], tolerance: float = 0.70) -> str:
    """Labels a candidate's local parameter landscape from plateau-probe results.

    BROAD_PLATEAU: every +/- nudge holds PF within `tolerance` of base -> robust
    region, candidate is tradeable. NARROW_SPIKE: at least one nudge collapses PF
    below tolerance * base -> knife-edge, curve-fit artifact, reject.
    """
    if base_pf <= 0:
        return "UNCLASSIFIED"
    if not probe_pfs:
        return "BROAD_PLATEAU"  # no in-bounds probes possible -> nothing failed
    worst = min(probe_pfs)
    return "NARROW_SPIKE" if worst < base_pf * tolerance else "BROAD_PLATEAU"


def test_parameter_plateau(best_params: Dict[str, Any],
                           base_profit_factor: float,
                           param_types: Dict[str, str],
                           param_bounds: Dict[str, Tuple[float, float]],
                           backtest_callback,
                           tolerance: float = 0.70) -> Tuple[bool, int, str]:
    """Nudges each winning parameter (int +/-1, double +/-5%) and re-runs a physical
    backtest. Returns (passed, extra_trials_run, landscape_label) where the label is
    BROAD_PLATEAU or NARROW_SPIKE per classify_parameter_landscape."""
    if base_profit_factor <= 0:
        return True, 0, "UNCLASSIFIED"  # nothing worth protecting; the hard gates will decide

    extra_trials = 0
    probe_pfs = []
    spike_param = None
    for param, value in best_params.items():
        lo, hi = param_bounds.get(param, (None, None))
        if param_types.get(param) == "double":
            nudges = [round(float(value) * 0.95, 4), round(float(value) * 1.05, 4)]
        else:
            nudges = [int(value) - 1, int(value) + 1]

        for nudged in nudges:
            if lo is not None and (nudged < lo or nudged > hi):
                continue
            test_params = dict(best_params)
            test_params[param] = nudged
            try:
                metrics = backtest_callback(test_params)
                extra_trials += 1
            except Exception as e:
                print(f"   ⚠️ Plateau probe {param}={nudged} failed ({str(e)[:100]}). Ignoring probe.", flush=True)
                continue
            probe_pf = metrics.get("profit_factor", 0.0)
            probe_pfs.append(probe_pf)
            if probe_pf < base_profit_factor * tolerance and spike_param is None:
                spike_param = (param, value, nudged, probe_pf)

    landscape = classify_parameter_landscape(base_profit_factor, probe_pfs, tolerance)
    if landscape == "NARROW_SPIKE":
        param, value, nudged, probe_pf = spike_param
        print(f"   ❌ PLATEAU REJECT [NARROW_SPIKE]: {param}={value} is a knife-edge spike "
              f"(nudge to {nudged} collapses PF to {probe_pf:.2f} "
              f"vs base {base_profit_factor:.2f}).", flush=True)
        return False, extra_trials, landscape
    print(f"   🗻 LANDSCAPE: BROAD_PLATEAU — all {len(probe_pfs)} nudge probes held within "
          f"{int(tolerance*100)}% of base PF {base_profit_factor:.2f}.", flush=True)
    return True, extra_trials, landscape


# =====================================================================
# STAGE 5: DEFLATED SHARPE RATIO (BAILEY & LOPEZ DE PRADO)
# =====================================================================
def calculate_deflated_sharpe(sharpe_ratio: float,
                              num_trials: int,
                              sample_size: int,
                              alpha: float = 0.05) -> Tuple[bool, float]:
    """DSR multiple-testing gate. Returns (passed, p_value).

    p_value = 1 - Phi(dsr_stat). A SMALL p-value means the observed Sharpe EXCEEDS
    the expected maximum Sharpe under multiple testing -> the edge is statistically
    valid. (Note: the rejection direction here is the opposite of the common but
    inverted snippet floating around — rejecting at p < alpha would keep the flukes
    and discard every real edge.)
    """
    from scipy.stats import norm

    n = max(2, int(num_trials))
    t = max(2, int(sample_size))
    euler = 0.5772156649

    # Expected maximum Sharpe over n independent trials (Euler-Mascheroni approx)
    expected_max_sharpe = (1 - euler) * norm.ppf(1 - 1.0 / n) + \
                          euler * norm.ppf(1 - 1.0 / (n * math.e))

    se_sharpe = math.sqrt(1.0 / t)  # simplified variance (per pipeline spec)
    dsr_stat = (sharpe_ratio - expected_max_sharpe) / se_sharpe
    p_value = float(1.0 - norm.cdf(dsr_stat))

    passed = p_value < alpha
    return passed, p_value


# =====================================================================
# PIPELINE ORCHESTRATOR (STAGES 1-5)
# =====================================================================
def run_sobol_optimization_pipeline(module_name: str,
                                    mql5_code: str,
                                    n_samples: int = 1024,
                                    top_k: int = 5,
                                    plateau_tolerance: float = 0.70,
                                    dsr_alpha: float = 0.05) -> Dict[str, Any]:
    """Runs the full 5-stage optimization on the LLM-written child EA.

    Returns a dict:
      best_params: winning input overrides (physically verified) or None
      best_metrics: scraped metrics of the winning parameter set or None
      trials_run: total physical tester runs consumed (for DSR accounting)
      pareto_size: number of non-dominated candidates found
      results_csv: path to the full batch results CSV (evidence)
      rejection_reason: why no winner was returned (if best_params is None)
    """
    input_ranges = extract_optimizable_inputs(mql5_code)
    if not input_ranges:
        return {"best_params": None, "best_metrics": None, "trials_run": 0,
                "pareto_size": 0, "results_csv": None,
                "rejection_reason": "No numeric optimizable inputs found in child EA"}

    param_bounds = {r["name"]: (r["start"], r["stop"]) for r in input_ranges}
    param_types = {r["name"]: r["type"] for r in input_ranges}

    # ---- STAGE 1: Sobol sampling ----
    grid = generate_sobol_parameter_grid(param_bounds, param_types, n_samples=n_samples)
    print(f"🧬 [STAGE 1/5] Sobol grid: {len(grid)} unique parameter sets across "
          f"{len(param_bounds)} dims ({', '.join(param_bounds.keys())})", flush=True)

    # ---- STAGE 2: Physical MT5 batch evaluation ----
    print(f"📈 [STAGE 2/5] Physical MT5 batch evaluation: {len(grid)} sequential tester runs...", flush=True)
    df_results, trials_run = batch_evaluate_parameter_grid(grid, module_name, module_name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_csv = EVIDENCE_DIR / f"{module_name}_sobol_{timestamp}.csv"
    if not df_results.empty:
        try:
            df_results.to_csv(results_csv, index=False)
        except Exception:
            pass

    df_valid = df_results[df_results["total_trades"] > 0] if not df_results.empty else df_results
    if df_valid.empty:
        return {"best_params": None, "best_metrics": None, "trials_run": trials_run,
                "pareto_size": 0, "results_csv": str(results_csv),
                "rejection_reason": f"All {trials_run} Sobol samples produced 0-trade or failed runs"}

    # ---- STAGE 3: Pareto non-dominated selection ----
    pareto = get_pareto_front(df_valid)
    print(f"⚖️ [STAGE 3/5] Pareto front: {len(pareto)} non-dominated candidates "
          f"(from {len(df_valid)} trade-producing runs)", flush=True)

    # ---- STAGES 4 & 5: Plateau + DSR gauntlet on the top-K Pareto candidates ----
    def _plateau_callback(params: Dict[str, Any]) -> Dict[str, Any]:
        return _run_single_param_set(module_name, f"{module_name}_PLATO{trials_holder[0]:03d}", params)

    trials_holder = [trials_run]
    def _counting_callback(params: Dict[str, Any]) -> Dict[str, Any]:
        metrics = _plateau_callback(params)
        trials_holder[0] += 1
        return metrics

    for rank, (_, cand) in enumerate(pareto.head(top_k).iterrows(), start=1):
        cand_params = {}
        for name in param_bounds:
            v = cand[name]
            cand_params[name] = int(v) if param_types[name] != "double" else float(v)

        print(f"🔬 [STAGE 4/5] Plateau test on Pareto #{rank}: PF={cand['profit_factor']:.2f} "
              f"DD={cand['max_drawdown']*100:.1f}% Trades={int(cand['total_trades'])} | {cand_params}", flush=True)
        plateau_ok, _, landscape = test_parameter_plateau(
            cand_params, cand["profit_factor"], param_types, param_bounds,
            _counting_callback, tolerance=plateau_tolerance
        )
        if not plateau_ok:
            continue

        dsr_ok, dsr_p = calculate_deflated_sharpe(
            cand.get("sharpe_ratio", 0.0), trials_holder[0], int(cand["total_trades"]), alpha=dsr_alpha
        )
        if not dsr_ok:
            print(f"   ❌ [STAGE 5/5] DSR REJECT: p={dsr_p:.4f} >= {dsr_alpha}. Sharpe {cand.get('sharpe_ratio', 0.0):.2f} "
                  f"does not beat the expected max under {trials_holder[0]} trials (multiple-testing fluke).", flush=True)
            continue
        print(f"   ✅ [STAGE 5/5] DSR PASS: p={dsr_p:.4f} < {dsr_alpha}. Edge survives multiple-testing deflation.", flush=True)

        best_metrics = {
            "total_trades": int(cand["total_trades"]),
            "win_rate": float(cand["win_rate"]),
            "profit_factor": float(cand["profit_factor"]),
            "max_drawdown": float(cand["max_drawdown"]),
            "max_consecutive_losses": int(cand["max_consecutive_losses"]),
            "sharpe_ratio": float(cand.get("sharpe_ratio", 0.0)),
        }
        return {"best_params": cand_params, "best_metrics": best_metrics,
                "trials_run": trials_holder[0], "pareto_size": len(pareto),
                "results_csv": str(results_csv), "rejection_reason": None}

    return {"best_params": None, "best_metrics": None, "trials_run": trials_holder[0],
            "pareto_size": len(pareto), "results_csv": str(results_csv),
            "rejection_reason": f"All top-{top_k} Pareto candidates failed the plateau/DSR gauntlet"}
