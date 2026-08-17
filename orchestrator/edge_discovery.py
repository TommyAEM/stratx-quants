"""
EDGE DISCOVERY ENGINE (PHASE_0 — the missing front-end of the quant desk).

A human quant does not start by mutating a strategy. They start by MINING THE
RAW DATA for conditional regularities: "given setup X occurred, what does price
do next, how often, and is it distinguishable from chance?" Only edges that
survive that screen earn a strategy build.

This module runs that screen deterministically over the physical broker bars
(data/vantage_ger40_m15_real.csv — 28,213 real Vantage M15 bars, the SAME data
the MT5 tester trades on). Pure stdlib + pandas/numpy. No LLM, no MT5 runs.

Screens implemented (each is a falsifiable anomaly candidate):
  1. SESSION EDGE MAP     — per-hour directional drift & volatility (in ATR)
  2. ASIA RANGE FAKEOUT   — sweep of Asia H/L then close back inside -> reversal
                            (this is literally the X1X_M1_FBO thesis, measured)
  3. PREV-DAY H/L SWEEP   — sweep of prior day high/low -> reversal
  4. OPEN MOMENTUM        — first-hour directional continuation after Frankfurt

Every screen reports: occurrences, win fraction, mean ATR-normalized forward
move, effect vs the unconditional baseline, exact binomial p-value, and a
Benjamini-Hochberg FDR flag across the whole screen family.

CLOCK HONESTY: broker server time != GMT. Every range-based screen runs under
BOTH plausible offsets (GMT+2 winter / GMT+3 summer) and reports both, so a
clock misalignment shows up as a measurable evidence gap instead of silently
poisoning session logic.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BARS_CSV = Path("C:/Trading/DE40-Research/data/vantage_ger40_m15_real.csv")
SCREEN_OUT = Path("C:/Trading/DE40-Research/evidence/edge_screen.json")

FWD_BARS = 16          # forward evaluation window (4 hours of M15)
ATR_LEN = 14
BREAK_ATR = 0.15       # min excursion beyond the level to count as a sweep
MAX_BARS_OUT = 8       # max bars outside the range before the fakeout is void
FDR_Q = 0.05


# --------------------------------------------------------------------- utils
def _binom_tail_pvalue(wins: int, n: int, p0: float = 0.5) -> float:
    """Exact one-sided binomial tail P(X >= wins | n, p0); normal approx for large n."""
    if n <= 0:
        return 1.0
    if n > 1000:
        # Normal approximation with continuity correction (exact tail overflows).
        mu, sd = n * p0, math.sqrt(n * p0 * (1 - p0))
        z = (wins - 0.5 - mu) / max(sd, 1e-9)
        return min(1.0, max(0.0, 0.5 * math.erfc(z / math.sqrt(2.0))))
    return min(1.0, sum(
        math.comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
        for k in range(wins, n + 1)))


def _bh_fdr(pvals: List[float], q: float = FDR_Q) -> List[bool]:
    """Benjamini-Hochberg significance flags."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    flags = [False] * m
    running_max = 0
    for rank, i in enumerate(order, 1):
        if pvals[i] <= (rank / m) * q:
            running_max = rank
    for rank, i in enumerate(order, 1):
        if rank <= running_max:
            flags[i] = True
    return flags


def load_bars(csv_path: Path = BARS_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    # Wilder ATR(14)
    pc = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]),
                    (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1.0 / ATR_LEN, adjust=False).mean()
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    return df


# ------------------------------------------------------------- screen 1: map
def screen_session_edge_map(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Per-hour unconditional drift & volatility in ATR units. This is the
    'where does the market actually move' map a human builds first."""
    rows = []
    closes = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    hours = df["hour"].to_numpy()
    n = len(df)
    for h in range(24):
        idx = np.where(hours == h)[0]
        idx = idx[idx + 4 < n]
        if len(idx) < 20:
            continue
        fwd = (closes[idx + 4] - closes[idx]) / np.maximum(atr[idx], 1e-9)
        rows.append({
            "hour": int(h),
            "n": int(len(idx)),
            "mean_fwd_atr": round(float(np.mean(fwd)), 3),
            "abs_drift_atr": round(float(np.mean(np.abs(fwd))), 3),
            "up_fraction": round(float(np.mean(fwd > 0)), 3),
        })
    return rows


# --------------------------------------- generic range-sweep-reversal screen
def _range_sweep_screen(df: pd.DataFrame, range_start_hour: int, range_end_hour: int,
                        label: str) -> Dict[str, Any]:
    """Sweep of an intraday range extreme followed by a close back inside ->
    measure the reversal move over the next FWD_BARS bars, in ATR units.
    Both directions pooled. This is the X1X FBO thesis, measured directly."""
    wins = 0
    fwd_moves: List[float] = []
    by_hour: Dict[int, List[float]] = {}

    times = df["time"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    hours = df["hour"].to_numpy()
    dates = df["date"].to_numpy()
    n = len(df)

    # Precompute per-date ranges for [range_start_hour, range_end_hour)
    day_ranges: Dict[Any, Tuple[float, float, int]] = {}
    for d in np.unique(dates):
        mask = (dates == d) & (hours >= range_start_hour) & (hours < range_end_hour)
        idx = np.where(mask)[0]
        if len(idx) >= 4:
            day_ranges[d] = (float(np.max(highs[idx])), float(np.min(lows[idx])), int(idx[-1]))

    unique_dates = list(np.unique(dates))
    for di, d in enumerate(unique_dates):
        if d not in day_ranges:
            continue
        r_hi, r_lo, range_end_idx = day_ranges[d]
        # Scan bars after the range completes for a sweep + close back inside
        j = range_end_idx + 1
        day_end = np.where(dates == d)[0][-1]
        while j <= day_end:
            a = max(atr[j], 1e-9)
            # bearish fakeout: break above range high then close back inside
            if highs[j] > r_hi + BREAK_ATR * a:
                k = j
                while k <= min(j + MAX_BARS_OUT, day_end):
                    if closes[k] < r_hi:
                        if k + FWD_BARS < n:
                            move = (closes[k] - closes[k + FWD_BARS]) / a  # short side
                            fwd_moves.append(float(move))
                            wins += 1 if move > 0 else 0
                            by_hour.setdefault(int(hours[k]), []).append(float(move))
                        j = k + 1
                        break
                    k += 1
                else:
                    j += 1
                    continue
                j = max(j, k + 1)
                continue
            # bullish fakeout: break below range low then close back inside
            if lows[j] < r_lo - BREAK_ATR * a:
                k = j
                while k <= min(j + MAX_BARS_OUT, day_end):
                    if closes[k] > r_lo:
                        if k + FWD_BARS < n:
                            move = (closes[k + FWD_BARS] - closes[k]) / a  # long side
                            fwd_moves.append(float(move))
                            wins += 1 if move > 0 else 0
                            by_hour.setdefault(int(hours[k]), []).append(float(move))
                        j = k + 1
                        break
                    k += 1
                else:
                    j += 1
                    continue
                j = max(j, k + 1)
                continue
            j += 1

    cnt = len(fwd_moves)
    if cnt == 0:
        return {"screen": label, "occurrences": 0, "win_rate": None,
                "mean_fwd_atr": None, "p_value": 1.0, "by_hour": {}}
    return {
        "screen": label,
        "occurrences": cnt,
        "win_rate": round(wins / cnt, 4),
        "mean_fwd_atr": round(float(np.mean(fwd_moves)), 3),
        "median_fwd_atr": round(float(np.median(fwd_moves)), 3),
        "p_value": _binom_tail_pvalue(wins, cnt),
        "by_hour": {h: {"n": len(v), "mean_fwd_atr": round(float(np.mean(v)), 3),
                        "win_rate": round(float(np.mean(np.array(v) > 0)), 3)}
                    for h, v in sorted(by_hour.items())},
    }


def screen_prev_day_sweep(df: pd.DataFrame, label: str) -> Dict[str, Any]:
    """Sweep of PRIOR DAY high/low then close back -> reversal move."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    hours = df["hour"].to_numpy()
    dates = df["date"].to_numpy()
    n = len(df)

    day_hl: Dict[Any, Tuple[float, float]] = {}
    for d in np.unique(dates):
        idx = np.where(dates == d)[0]
        day_hl[d] = (float(np.max(highs[idx])), float(np.min(lows[idx])))

    unique_dates = list(np.unique(dates))
    wins = 0
    fwd_moves: List[float] = []
    by_hour: Dict[int, List[float]] = {}
    for di in range(1, len(unique_dates)):
        d = unique_dates[di]
        pdh, pdl = day_hl[unique_dates[di - 1]]
        day_idx = np.where(dates == d)[0]
        for j in day_idx:
            a = max(atr[j], 1e-9)
            direction = 0
            if highs[j] > pdh + BREAK_ATR * a and closes[j] < pdh:
                direction = -1  # swept prior high, closed back below -> short
            elif lows[j] < pdl - BREAK_ATR * a and closes[j] > pdl:
                direction = 1
            if direction != 0 and j + FWD_BARS < n:
                move = direction * (closes[j + FWD_BARS] - closes[j]) / a
                fwd_moves.append(float(move))
                wins += 1 if move > 0 else 0
                by_hour.setdefault(int(hours[j]), []).append(float(move))

    cnt = len(fwd_moves)
    if cnt == 0:
        return {"screen": label, "occurrences": 0, "win_rate": None,
                "mean_fwd_atr": None, "p_value": 1.0, "by_hour": {}}
    return {
        "screen": label,
        "occurrences": cnt,
        "win_rate": round(wins / cnt, 4),
        "mean_fwd_atr": round(float(np.mean(fwd_moves)), 3),
        "median_fwd_atr": round(float(np.median(fwd_moves)), 3),
        "p_value": _binom_tail_pvalue(wins, cnt),
        "by_hour": {h: {"n": len(v), "mean_fwd_atr": round(float(np.mean(v)), 3),
                        "win_rate": round(float(np.mean(np.array(v) > 0)), 3)}
                    for h, v in sorted(by_hour.items())},
    }


def screen_open_momentum(df: pd.DataFrame, open_hour: int, label: str) -> Dict[str, Any]:
    """Frankfurt-open continuation: direction of the first hour predicts the
    next 4 hours? Measured in ATR units."""
    closes = df["close"].to_numpy()
    opens = df["open"].to_numpy()
    atr = df["atr"].to_numpy()
    hours = df["hour"].to_numpy()
    n = len(df)
    idx = np.where(hours == open_hour)[0]
    idx = idx[idx + FWD_BARS < n]
    wins = 0
    moves: List[float] = []
    for j in idx:
        a = max(atr[j], 1e-9)
        first_bar_dir = np.sign(closes[j] - opens[j])
        if first_bar_dir == 0:
            continue
        move = first_bar_dir * (closes[j + FWD_BARS] - closes[j]) / a
        moves.append(float(move))
        wins += 1 if move > 0 else 0
    cnt = len(moves)
    if cnt == 0:
        return {"screen": label, "occurrences": 0, "win_rate": None,
                "mean_fwd_atr": None, "p_value": 1.0, "by_hour": {}}
    return {
        "screen": label,
        "occurrences": cnt,
        "win_rate": round(wins / cnt, 4),
        "mean_fwd_atr": round(float(np.mean(moves)), 3),
        "median_fwd_atr": round(float(np.median(moves)), 3),
        "p_value": _binom_tail_pvalue(wins, cnt),
        "by_hour": {},
    }


# ------------------------------------------------------------------- driver
def run_edge_screen(csv_path: Path = BARS_CSV, out_path: Path = SCREEN_OUT,
                    verbose: bool = True) -> Dict[str, Any]:
    df = load_bars(csv_path)

    session_map = screen_session_edge_map(df)

    # Range screens under BOTH broker-clock hypotheses (honesty about the offset):
    #   GMT+2: Asia 00-07 GMT = broker 02-09 ; Frankfurt 07 GMT = broker 09
    #   GMT+3: Asia 00-07 GMT = broker 03-10 ; Frankfurt 07 GMT = broker 10
    screens = [
        _range_sweep_screen(df, 2, 9, "ASIA_FAKEOUT_REVERSAL (clock=GMT+2)"),
        _range_sweep_screen(df, 3, 10, "ASIA_FAKEOUT_REVERSAL (clock=GMT+3)"),
        _range_sweep_screen(df, 0, 7, "ASIA_FAKEOUT_REVERSAL (clock=as-is)"),
        screen_prev_day_sweep(df, "PREV_DAY_HL_SWEEP_REVERSAL"),
        screen_open_momentum(df, 9, "FRANKFURT_OPEN_MOMENTUM (clock=GMT+2)"),
        screen_open_momentum(df, 10, "FRANKFURT_OPEN_MOMENTUM (clock=GMT+3)"),
    ]

    # BH-FDR across the screen family
    pvals = [s["p_value"] for s in screens]
    fdr_flags = _bh_fdr(pvals)
    for s, f in zip(screens, fdr_flags):
        s["fdr_significant"] = bool(f)

    # Unconditional baseline for effect-size comparison
    closes = df["close"].to_numpy()
    atr = df["atr"].to_numpy()
    base_fwd = np.abs(closes[FWD_BARS:] - closes[:-FWD_BARS]) / np.maximum(atr[:-FWD_BARS], 1e-9)
    baseline = {"mean_abs_fwd_atr": round(float(np.mean(base_fwd)), 3),
                "up_fraction": round(float(np.mean((closes[FWD_BARS:] - closes[:-FWD_BARS]) > 0)), 3)}

    ranked = sorted(
        [s for s in screens if s["occurrences"] > 0],
        key=lambda s: (s["fdr_significant"], s["occurrences"], abs(s.get("mean_fwd_atr") or 0)),
        reverse=True)

    out = {
        "data": {"file": str(csv_path), "bars": int(len(df)),
                 "from": str(df["time"].iloc[0]), "to": str(df["time"].iloc[-1])},
        "baseline": baseline,
        "session_edge_map": session_map,
        "screens": screens,
        "ranked_edges": [{"screen": s["screen"], "occurrences": s["occurrences"],
                          "win_rate": s["win_rate"], "mean_fwd_atr": s["mean_fwd_atr"],
                          "p_value": round(s["p_value"], 5),
                          "fdr_significant": s["fdr_significant"]} for s in ranked],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    if verbose:
        print("\n" + "=" * 80, flush=True)
        print("🔬 [PHASE_0 EDGE DISCOVERY SCREEN — measured on real broker bars]", flush=True)
        print(f"   Data: {out['data']['bars']} bars | {out['data']['from']} -> {out['data']['to']}", flush=True)
        print(f"   Baseline: mean |4h move| = {baseline['mean_abs_fwd_atr']} ATR | "
              f"up-fraction {baseline['up_fraction']*100:.1f}%", flush=True)
        print("   RANKED CANDIDATE EDGES:", flush=True)
        for s in ranked:
            flag = "✅ FDR-SIGNIFICANT" if s["fdr_significant"] else "—"
            print(f"     {s['screen']}: n={s['occurrences']} WR={s['win_rate']} "
                  f"fwd={s['mean_fwd_atr']}ATR p={s['p_value']:.4f} {flag}", flush=True)
        print("=" * 80 + "\n", flush=True)
    return out


def format_edge_screen_block(screen: Optional[Dict[str, Any]], max_edges: int = 4) -> str:
    """Renders the discovery screen for council/forensic prompts (neutral, factual)."""
    if not screen:
        return "[EDGE DISCOVERY SCREEN]: not run."
    lines = [f"[EDGE DISCOVERY SCREEN — measured on {screen['data']['bars']} real broker bars "
             f"({screen['data']['from'][:10]} -> {screen['data']['to'][:10]})]:"]
    for e in screen.get("ranked_edges", [])[:max_edges]:
        sig = "FDR-SIGNIFICANT" if e["fdr_significant"] else "not significant"
        lines.append(f"  • {e['screen']}: n={e['occurrences']} WR={e['win_rate']} "
                     f"fwd={e['mean_fwd_atr']}ATR p={e['p_value']} ({sig})")
    if not screen.get("ranked_edges"):
        lines.append("  • No anomaly candidate reached measurable frequency on this data.")
    return "\n".join(lines)


if __name__ == "__main__":
    run_edge_screen()
