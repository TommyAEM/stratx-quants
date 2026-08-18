"""
PROTOTYPE LAB — STAGE 1 of the StratX strategy funnel.

The missing middle between PHASE_0 discovery (measured anomaly) and the
physical MT5 loop (expensive). A hypothesis is simulated DIRECTLY on the
28k real broker bars — no MQL5 generation, no MetaEditor, no MT5 terminal,
no LLM calls. Hundreds of parameter variants cost seconds, so a thesis can
be KILLED or SEEDED with its best measured region before a single MT5 run
is burned.

Funnel:
    STAGE 0  edge_discovery screen      (is there a measured anomaly?)
    STAGE 1  prototype_lab grid         (does ANY parameter region survive
                                         costs with acceptable RR/DD?)
    STAGE 2  MT5 physical backtest      (confirm the seeded region)
    STAGE 3+ self-heal / WF / review    (existing machinery)

Deterministic: same CSV + same params -> identical metrics. No randomness.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from orchestrator.edge_discovery import load_bars, BARS_CSV
except ImportError:  # direct script execution from repo root
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from orchestrator.edge_discovery import load_bars, BARS_CSV

MAX_HOLD_BARS = 96        # 24h of M15 — a continuation trade that hasn't resolved by then is dead
COST_R = 0.08             # spread + slippage haircut per trade, in R units (conservative)
PROTO_OUT = Path(__file__).parent.parent / "evidence" / "prototype_grid_X1X_M1_PDC.json"


def simulate_pdc(df: pd.DataFrame,
                 stop_atr: float = 1.0,
                 target_rr: float = 2.0,
                 min_beyond_atr: float = 0.10,
                 disp_body_atr: float = 0.30,
                 max_ext_atr: float = 1.50,
                 start_hour: int = 7,
                 end_hour: int = 16,
                 max_daily_losses: int = 3,
                 cost_r: float = COST_R) -> Dict[str, Any]:
    """
    Prior-day sweep CONTINUATION prototype (mirrors X1X_M1_PDC semantics):
      signal bar closes beyond PDH/PDL by >= min_beyond_atr ATR with a
      displacement body, not over-extended; entry at next bar open;
      SL = stop_atr x ATR, TP = target_rr x stop; same-bar stop checked
      FIRST (conservative); one position at a time; daily loss breaker.
    Returns full metric bundle in R units (costs included).
    """
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = df["atr"].to_numpy(dtype=float)
    hours = df["hour"].to_numpy(dtype=int)
    dates = df["date"].to_numpy()

    # Prior completed day's high/low for every bar
    day_hi = df.groupby("date")["high"].max()
    day_lo = df.groupby("date")["low"].min()
    pdh_map = day_hi.shift(1).to_dict()
    pdl_map = day_lo.shift(1).to_dict()

    n = len(df)
    rs: List[float] = []
    day_losses: Dict[Any, int] = {}
    i = 1
    while i < n - 2:
        a = atr[i]
        if a <= 0 or np.isnan(a):
            i += 1
            continue
        d = dates[i]
        pdh = pdh_map.get(d)
        pdl = pdl_map.get(d)
        if pdh is None or pdl is None:
            i += 1
            continue
        if max_daily_losses > 0 and day_losses.get(d, 0) >= max_daily_losses:
            i += 1
            continue
        hr = int(hours[i])
        if not (start_hour <= hr < end_hour):
            i += 1
            continue
        body = abs(c[i] - o[i])
        direction = 0
        if (c[i] > pdh + min_beyond_atr * a and body >= disp_body_atr * a
                and c[i] > o[i] and (c[i] - pdh) <= max_ext_atr * a):
            direction = 1
        elif (c[i] < pdl - min_beyond_atr * a and body >= disp_body_atr * a
                and c[i] < o[i] and (pdl - c[i]) <= max_ext_atr * a):
            direction = -1
        if direction == 0:
            i += 1
            continue

        entry = o[i + 1]
        stop_dist = stop_atr * a
        stop = entry - direction * stop_dist
        target = entry + direction * target_rr * stop_dist

        r = None
        exit_idx = None
        j = i + 1
        while j < min(i + 1 + MAX_HOLD_BARS, n):
            hit_stop = l[j] <= stop if direction == 1 else h[j] >= stop
            hit_target = h[j] >= target if direction == 1 else l[j] <= target
            if hit_stop:                       # conservative: stop first
                r = -1.0
                exit_idx = j
                break
            if hit_target:
                r = float(target_rr)
                exit_idx = j
                break
            j += 1
        if r is None:                          # time exit at close
            j = min(i + MAX_HOLD_BARS, n - 1)
            r = direction * (c[j] - entry) / stop_dist
            exit_idx = j

        r_net = r - cost_r
        rs.append(r_net)
        if r_net < 0:
            day_losses[d] = day_losses.get(d, 0) + 1
        i = exit_idx + 1                       # one position at a time

    return metrics_from_r(rs, df)


def metrics_from_r(rs: List[float], df: pd.DataFrame) -> Dict[str, Any]:
    """Metrics bundle in R units (per-trade risk normalised to 1R)."""
    n_days = max((df["date"].iloc[-1] - df["date"].iloc[0]).days, 1)
    years = n_days / 365.25
    if not rs:
        return {"n": 0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy_r": 0.0,
                "payoff": 0.0, "max_dd_r": 0.0, "trades_per_year": 0.0, "total_r": 0.0}
    arr = np.asarray(rs, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    gross_w = float(wins.sum())
    gross_l = float(-losses.sum())
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    max_dd = float((peak - cum).max()) if len(cum) else 0.0
    return {
        "n": len(rs),
        "win_rate": round(float(len(wins) / len(arr)), 4),
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else 99.0,
        "expectancy_r": round(float(arr.mean()), 4),
        "payoff": round(float(wins.mean() / -losses.mean()), 3) if len(wins) and len(losses) else 0.0,
        "max_dd_r": round(max_dd, 2),
        "total_r": round(float(arr.sum()), 2),
        "trades_per_year": round(len(rs) / years, 1),
    }


def run_pdc_grid(df: pd.DataFrame, verbose: bool = True) -> List[Dict[str, Any]]:
    """Full parameter landscape for the PDC hypothesis — the cheap map that
    decides whether this thesis deserves ANY MT5 burn, and if so, where."""
    grid = []
    for stop in (0.50, 0.75, 1.00, 1.50):
        for rr in (1.5, 2.0, 3.0):
            for disp in (0.20, 0.30, 0.50):
                for beyond in (0.05, 0.10, 0.20):
                    for (h0, h1) in ((7, 16), (8, 16), (8, 12), (9, 16)):
                        for loss_cap in (3, 0):      # 0 = breaker off
                            m = simulate_pdc(df, stop_atr=stop, target_rr=rr,
                                             min_beyond_atr=beyond, disp_body_atr=disp,
                                             max_ext_atr=1.50, start_hour=h0, end_hour=h1,
                                             max_daily_losses=loss_cap)
                            grid.append({"stop_atr": stop, "target_rr": rr, "disp_body_atr": disp,
                                         "min_beyond_atr": beyond, "session": f"{h0}-{h1}",
                                         "daily_loss_cap": loss_cap, **m})
    grid.sort(key=lambda g: (g["expectancy_r"] if g["n"] >= 30 else -9e9), reverse=True)
    return grid


def viable_region(grid: List[Dict[str, Any]],
                  min_n: int = 100, min_pf: float = 1.30,
                  min_expectancy_r: float = 0.05) -> Optional[Dict[str, Any]]:
    """STAGE 1 pass bar: enough sample, real expectancy after costs, and a
    profit factor with headroom over the physical-test haircut. Returns the
    best viable cell or None (thesis shelved before any MT5 burn)."""
    viable = [g for g in grid if g["n"] >= min_n and g["profit_factor"] >= min_pf
              and g["expectancy_r"] >= min_expectancy_r]
    return viable[0] if viable else None


def format_grid_report(grid: List[Dict[str, Any]], top: int = 8) -> str:
    lines = ["stop  RR   disp  beyond  sess    cap |     N    WR%     PF   expR  payoff  maxDDR   N/yr"]
    for g in grid[:top]:
        lines.append(
            f"{g['stop_atr']:.2f}  {g['target_rr']:.1f}  {g['disp_body_atr']:.2f}  {g['min_beyond_atr']:.2f}   "
            f"{g['session']:>5}  {g['daily_loss_cap']:>3} | {g['n']:>5}  {g['win_rate']*100:5.1f}  "
            f"{g['profit_factor']:5.2f}  {g['expectancy_r']:+.3f}  {g['payoff']:5.2f}  "
            f"{g['max_dd_r']:6.1f}  {g['trades_per_year']:6.1f}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    df = load_bars(BARS_CSV)
    print(f"Loaded {len(df)} bars. Running PDC prototype grid (864 variants, no MT5)...", flush=True)
    grid = run_pdc_grid(df, verbose=False)
    best = viable_region(grid)
    print()
    print(format_grid_report(grid))
    print()
    if best:
        print(f"VIABLE REGION: {best}")
    else:
        print("NO VIABLE REGION — thesis shelved at STAGE 1 (zero MT5 compute burned).")
    PROTO_OUT.write_text(json.dumps({"grid": grid, "viable": best}, indent=1))
    print(f"\nCached -> {PROTO_OUT}")
