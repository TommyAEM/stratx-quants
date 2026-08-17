#!/usr/bin/env python
"""DE40 campaign WAVE P1 · Step 15: Sobol pre-screen over 6 SOT v4.0 GER40 params.

Sobol-256 scan over the supervisor-staged param ranges, evaluated on the DEV
window split into 3 consecutive folds (entry-time partitioned single run per
config).  A config passes the pre-screen when its per-fold OOS expectancy (R) is
positive on >=2 of 3 folds; the top-20 by mean OOS expectancy are written to
evidence/sot_sobol_top20.json.

Method note: 256 points via scipy.stats.qmc.Sobol (scramble=True) — the full
quasi-Monte-Carlo Sobol sequence, not an LHS fallback.
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from scipy.stats import qmc

# ---- reuse the prescreen's engine wiring + config loader ----
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from sot_prescreen import (  # noqa: E402
    load_config_and_overrides,
    collect_unmapped_keys,
    ENGINE_PY,
    REPO_ROOT,
    SYMBOL,
    TV_WINDOW_MS,
    VERIFIED_CONFIG_PATH,
    OUTPUT_DIR,
)
from config import Config  # noqa: E402
from feed_bars import resolve_feed, bars_from_csv  # noqa: E402
from orchestrator import run_backtest  # noqa: E402

# ---- scan definition ----
# (pine_label, engine_field, low, high, dtype)
PARAM_SPECS = [
    ("SL ATR Mult / Liquidity Buffer", "atr_mult", 1.4, 2.2, float),
    ("Goldilocks Lower", "gl_lower", 0.020, 0.040, float),
    ("Goldilocks Upper", "gl_upper", 0.50, 0.80, float),
    ("Goldilocks Duration (bars)", "gl_duration", 18, 28, int),
    ("Intensity Smoothing Length", "intensity_smooth_len", 5, 9, int),
    ("Impulse Size x Avg Body", "disp_mult", 1.2, 1.6, float),
]
N_POINTS = 256
N_FOLDS = 3
TOP_N = 20

OUT_JSON = os.path.join(OUTPUT_DIR, "sot_sobol_top20.json")


def sobol_points(n: int, d: int, seed: int = 42):
    """n Sobol points in [0,1]^d (scramble=True, seed fixed for determinism)."""
    engine = qmc.Sobol(d=d, scramble=True, seed=seed)
    return engine.random(n)


def scale_point(u: np.ndarray):
    """Scale a unit-cube point to the param ranges, returning label->value dict."""
    out = {}
    for i, (label, _field, lo, hi, dtype) in enumerate(PARAM_SPECS):
        v = lo + u[i] * (hi - lo)
        out[label] = dtype(round(v, 4)) if dtype is int else float(round(v, 6))
    return out


def fold_expectancies(trades, fold_bounds):
    """Per-fold mean R over closed trades, partitioned by ENTRY bar time.

    Each trade's entry time = bars["time"][t["bar"]].  OPEN trades (never
    resolved) are excluded from the expectancy denominator (mirrors the engine's
    metrics: OPEN counts in total trades but never as a win / never in R sums).
    Returns (expectancies, trades_per_fold) both length N_FOLDS; a fold with no
    closed trades gets expectancy None.
    """
    exp = [None] * N_FOLDS
    cnt = [0] * N_FOLDS
    for t in trades:
        if t.get("reason") == "OPEN":
            continue
        entry_t = t["_entry_ms"]
        for fi, (lo, hi) in enumerate(fold_bounds):
            if lo <= entry_t <= hi:
                cnt[fi] += 1
                exp[fi] = (exp[fi] or 0.0) + t["r"]
                break
    out_exp = []
    for fi in range(N_FOLDS):
        if cnt[fi] > 0:
            out_exp.append(exp[fi] / cnt[fi])
        else:
            out_exp.append(None)
    return out_exp, cnt


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    t0 = time.time()

    # ---- load verified config + feed once ----
    with open(VERIFIED_CONFIG_PATH, encoding="utf-8") as f:
        verified = json.load(f)
    raw_config = verified["config"]

    feed_path = resolve_feed(SYMBOL)
    if feed_path is None:
        print("ERROR: resolve_feed returned None")
        sys.exit(1)
    bars, df = bars_from_csv(feed_path)
    times_ms = bars["time"]
    n_bars = len(times_ms)
    print(f"Feed: {feed_path}  ({n_bars} bars, "
          f"{datetime.fromtimestamp(times_ms[0]/1000, tz=timezone.utc):%Y-%m-%d} .. "
          f"{datetime.fromtimestamp(times_ms[-1]/1000, tz=timezone.utc):%Y-%m-%d})")

    # ---- 3 consecutive folds over the DEV window ----
    w0, w1 = TV_WINDOW_MS
    span = w1 - w0
    fold_bounds = [(w0 + fi * span // N_FOLDS, w0 + (fi + 1) * span // N_FOLDS)
                   for fi in range(N_FOLDS)]
    for fi, (lo, hi) in enumerate(fold_bounds):
        print(f"  fold {fi+1}: {datetime.fromtimestamp(lo/1000, tz=timezone.utc):%Y-%m-%d} .. "
              f"{datetime.fromtimestamp(hi/1000, tz=timezone.utc):%Y-%m-%d}")

    # ---- base config sanity: unmapped keys of the canonical map ----
    unmapped = collect_unmapped_keys(raw_config)
    print(f"Unmapped config keys (base): {len(unmapped)}")

    # ---- Sobol points ----
    pts = sobol_points(N_POINTS, len(PARAM_SPECS))
    print(f"Sobol points: {len(pts)} x {len(PARAM_SPECS)} params (scipy qmc, scramble=True)")

    results = []
    for idx in range(N_POINTS):
        overrides = scale_point(pts[idx])
        # full config = verified GER40 map + this point's 6 overrides
        cfg_overrides = dict(raw_config)
        cfg_overrides.update(overrides)
        cfg = load_config_and_overrides(cfg_overrides, SYMBOL)
        cfg.start_date = w0
        cfg.end_date = w1

        out = run_backtest(bars, cfg, confluence_bars=None, collect_debug=False)
        trades = out["trades"]
        # stamp entry ms for fold partition
        for t in trades:
            t["_entry_ms"] = times_ms[t["bar"]]

        exp, cnt = fold_expectancies(trades, fold_bounds)
        closed = [t for t in trades if t.get("reason") != "OPEN"]
        n_positive = sum(1 for e in exp if e is not None and e > 0)
        valid = [e for e in exp if e is not None]
        mean_oos = sum(valid) / len(valid) if valid else None

        results.append({
            "config_id": f"sot_sobol_{idx+1:04d}",
            "params": overrides,
            "fold_expectancies": exp,
            "mean_oos_expectancy": mean_oos,
            "trades_per_fold": cnt,
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "n_positive_folds": n_positive,
        })

        if (idx + 1) % 32 == 0:
            print(f"  {idx+1}/{N_POINTS} evaluated "
                  f"({time.time()-t0:.0f}s elapsed)")

    # ---- pre-screen filter: positive expectancy on >=2 of 3 folds ----
    passed = [r for r in results
              if r["mean_oos_expectancy"] is not None and r["n_positive_folds"] >= 2]
    passed.sort(key=lambda r: r["mean_oos_expectancy"], reverse=True)
    top20 = passed[:TOP_N]

    print(f"\nConfigs with >=2/3 positive folds: {len(passed)}")
    print(f"Top-20 mean OOS expectancy: "
          f"{top20[-1]['mean_oos_expectancy']:.4f} .. "
          f"{top20[0]['mean_oos_expectancy']:.4f} R")

    summary = {
        "task": "sot_sobol_prescreen",
        "method": "sobol (scipy.stats.qmc.Sobol, scramble=True, seed=42)",
        "n_points": N_POINTS,
        "n_folds": N_FOLDS,
        "fold_mode": "3 consecutive folds over DEV window, entry-time partitioned "
                     "single run per config (no per-fold training; pre-screen)",
        "window_ms": {"start": w0, "end": w1},
        "feed_path": feed_path,
        "feed_rows": n_bars,
        "param_specs": [
            {"label": label, "field": field, "low": lo, "high": hi, "dtype": dtype.__name__}
            for label, field, lo, hi, dtype in PARAM_SPECS
        ],
        "base_config_unmapped_keys": unmapped,
        "filter": "positive fold expectancy on >=2 of 3 folds",
        "top20_count": len(top20),
        "passed_count": len(passed),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "top20": top20,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {OUT_JSON} ({len(top20)} entries) in {time.time()-t0:.0f}s")

    best = top20[0] if top20 else None
    print("\nBEST CONFIG:")
    if best:
        for k, v in best["params"].items():
            print(f"  {k}: {v}")
        print(f"  mean OOS expectancy: {best['mean_oos_expectancy']:.4f} R")
        print(f"  fold expectancies: {[round(e,4) if e is not None else None for e in best['fold_expectancies']]}")
        print(f"  trades per fold: {best['trades_per_fold']}")
    else:
        print("  none passed the >=2/3 positive-fold filter")

    return summary


if __name__ == "__main__":
    summary = main()
    top20 = summary["top20"]
    if top20:
        lo = top20[-1]["mean_oos_expectancy"]
        hi = top20[0]["mean_oos_expectancy"]
        best = top20[0]
        print(f"\nFINAL: method={summary['method'].split(' ')[0]} "
              f"top20-mean-exp={lo:.4f}..{hi:.4f}R "
              f"best-params={json.dumps(best['params'])} "
              f"evidence={OUT_JSON}")
    else:
        print(f"\nFINAL: method=sobol top20=EMPTY evidence={OUT_JSON}")