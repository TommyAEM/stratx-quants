#!/usr/bin/env python
"""DE40 campaign WAVE P1: Python pre-screen of TV-verified SOT v4.0 GER40 config.

Loads the OANDA GER40 pinned CSV, builds the full verified Config (sessions,
days, scalars, confluence), gates to the TV backtest window, runs through the
canonical Engine X orchestrator, and writes a trade ledger + summary JSON.

Reference truth (TV, OANDA feed): 51 trades, WR 74.51%, PF 3.491, DD 3.12%.
"""
import json
import os
import sys
import math
from datetime import datetime, timezone

# ---- engine imports ----
ENGINE_PY = r"C:\Trading\Terminal-X-V2-Recovered\engine_py"
REPO_ROOT = r"C:\Trading\Terminal-X-V2-Recovered"
if ENGINE_PY not in sys.path:
    sys.path.insert(0, ENGINE_PY)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from config import Config, _LABEL_MAP, load_overrides
from feed_bars import resolve_feed, bars_from_csv
from orchestrator import run_backtest
from gates import in_backtest_window

# Also use verified_configs helper for full session/day parsing
from verified_configs import (
    load_verified_config,
    _SESSIONS,
    _DAYS,
    _COSMETIC_LABELS,
    _REVIEWED_NOT_MAPPED_LABELS,
    _LABEL_FIELD as VC_LABEL_FIELD,
)

# ---- constants ----
SYMBOL = "GER40"
TV_WINDOW_MS = (1754007300000, 1782953100000)  # [start, end] epoch ms
TV_REF = {"trades": 51, "wr": 74.51, "pf": 3.491, "dd_pct": 3.12}
VERIFIED_CONFIG_PATH = r"C:\Trading\Terminal-X-V2-Recovered\verified_configs\GER40.json"
OUTPUT_DIR = r"C:\Trading\DE40-Research\evidence"


def load_config_and_overrides(raw_config: dict, symbol: str) -> Config:
    """Build a Config from GATED defaults + Pine-label overrides in raw_config.

    Uses config.load_overrides for the _LABEL_MAP entries, then applies the
    richer verified_configs._LABEL_FIELD for keys NOT covered by load_overrides
    (impulse_mult, atr_len, br_tolerance_atr, etc.), and manually wires sessions,
    days, and news windows.
    Prints warnings for any unmapped keys.
    """
    from verified_configs import _LABEL_FIELD as VC_LABEL_FIELD

    cfg = Config()

    # Step 1: apply scalar overrides via the canonical load_overrides
    load_overrides(cfg, raw_config, symbol)

    # Step 1b: apply verified_configs _LABEL_FIELD entries NOT already in
    # config._LABEL_MAP (load_overrides only covers ~29 labels; the full
    # canonical map has ~64).  Without this, impulse_mult, atr_len,
    # br_tolerance_atr, disp_mult, fvg_max_bars etc. stay at GATED defaults
    # and the engine diverges from TV (GER40: 38 vs 51 trades).
    already_set = set(_LABEL_MAP.keys())
    for label, field in VC_LABEL_FIELD.items():
        if label in raw_config and label not in already_set:
            val = raw_config[label]
            cur = getattr(cfg, field, None)
            try:
                if isinstance(cur, bool):
                    val = bool(val)
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    val = int(val)
                elif isinstance(cur, float):
                    val = float(val)
                setattr(cfg, field, val)
            except (TypeError, ValueError):
                pass

    # Step 2: sessions (7-slot GATED order matching Config.sessions default)
    sess_slots = [
        ("Use Main Session Window", "Main Session Window UTC"),
        ("Asia Open", "Asia Open UTC"),
        ("London Open", "London Open UTC"),
        ("New York Open", "New York Open UTC"),
        ("Asia Kill Zone", "Asia Kill Zone UTC"),
        ("London Kill Zone", "London Kill Zone UTC"),
        ("New York Kill Zone", "New York Kill Zone UTC"),
    ]
    sess_out = []
    for i, (en_lab, win_lab) in enumerate(sess_slots):
        if win_lab in raw_config:
            sess_out.append(
                (bool(raw_config.get(en_lab, True)), str(raw_config.get(win_lab, "")))
            )
        elif i < len(cfg.sessions):
            sess_out.append(cfg.sessions[i])
    cfg.sessions = sess_out

    # Step 3: days
    day_labels = [
        ("Monday", "mon"),
        ("Tuesday", "tue"),
        ("Wednesday", "wed"),
        ("Thursday", "thu"),
        ("Friday", "fri"),
        ("Saturday", "sat"),
        ("Sunday", "sun"),
    ]
    if any(dl in raw_config for dl, _ in day_labels):
        cfg.days = {
            dk: bool(raw_config.get(dl, cfg.days.get(dk, False)))
            for dl, dk in day_labels
        }

    # Step 4: news windows (cosmetic-only in Pine, but keep for parity)
    nw1_en = raw_config.get("News Window 1")
    nw1_win = raw_config.get("News Window 1 UTC")
    if nw1_win:
        cfg.news_windows = [
            (bool(nw1_en), str(nw1_win))
        ] + cfg.news_windows[1:]

    return cfg


def collect_unmapped_keys(raw_config: dict) -> list[str]:
    """Return sorted list of canonical-config keys the engine does NOT consume.

    Cross-references against _LABEL_MAP (config.py), verified_configs' own
    _LABEL_FIELD, session/day labels, cosmetic labels, and reviewed-unmapped
    labels.  Keys NOT in any of these sets are genuinely unmapped.
    """
    from verified_configs import (
        _SESSIONS as VC_SESSIONS,
        _DAYS as VC_DAYS,
        _COSMETIC_LABELS as VC_COSMETIC,
        _REVIEWED_NOT_MAPPED_LABELS as VC_REVIEWED,
        _LABEL_FIELD as VC_FIELD,
    )

    consumed = set()
    # All load_overrides _LABEL_MAP keys
    consumed.update(_LABEL_MAP.keys())
    # Verified_configs scalar labels (superset of _LABEL_MAP)
    consumed.update(VC_FIELD.keys())
    # Session enabler + window labels
    for en_lab, win_lab in VC_SESSIONS:
        consumed.add(en_lab)
        consumed.add(win_lab)
    # Day labels
    for dl, _ in VC_DAYS:
        consumed.add(dl)
    # Cosmetic / reviewed-unmapped
    consumed.update(VC_COSMETIC.keys())
    consumed.update(VC_REVIEWED.keys())

    unmapped = sorted(k for k in raw_config if k not in consumed)
    return unmapped


def compute_dd_pct(r_list, risk_pct, symbol_vol_mult=1.0, equity=10000.0):
    """Compute max drawdown as % of equity from per-trade R-multiples.

    Mirrors search.compute_max_dd_pct.
    """
    if not r_list:
        return None
    adj_risk = risk_pct * symbol_vol_mult
    risk_cash = equity * adj_risk / 100.0
    eq = equity
    peak = equity
    max_dd = 0.0
    for r in r_list:
        eq += r * risk_cash
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- 1. Load config JSON ----
    with open(VERIFIED_CONFIG_PATH, encoding="utf-8") as f:
        verified = json.load(f)

    raw_config = verified["config"]
    tv_res = verified.get("tv_confirmed_results", {})
    feed_declared = verified.get("feed", "unknown")

    print(f"=== SOT v4.0 GER40 Python Prescreen ===")
    print(f"Config captured: {verified.get('captured_at', '?')}")
    print(f"TV reference: {tv_res.get('trades', '?')} trades, "
          f"WR {tv_res.get('wr', '?')}%, PF {tv_res.get('pf', '?')}, "
          f"DD {tv_res.get('dd_pct', '?')}%")
    print(f"Window: {TV_WINDOW_MS}")
    print(f"Feed: {feed_declared}")
    print()

    # ---- 2. Load bars ----
    feed_path = resolve_feed(SYMBOL)
    if feed_path is None:
        print(f"ERROR: resolve_feed('{SYMBOL}') returned None")
        sys.exit(1)

    print(f"Feed path: {feed_path}")
    bars, df = bars_from_csv(feed_path)
    print(f"Loaded {len(bars['time'])} bars, "
          f"time range: {datetime.fromtimestamp(bars['time'][0]/1000, tz=timezone.utc)} "
          f"to {datetime.fromtimestamp(bars['time'][-1]/1000, tz=timezone.utc)}")
    print()

    # ---- 3. Build Config ----
    cfg = load_config_and_overrides(raw_config, SYMBOL)

    # ---- 4. Restrict backtest window ----
    start_ms, end_ms = TV_WINDOW_MS
    cfg.start_date = start_ms
    cfg.end_date = end_ms
    print(f"Backtest window: {cfg.start_date} .. {cfg.end_date}")

    # Count bars in window
    bars_in_window = sum(
        1 for t in bars["time"]
        if in_backtest_window(t, cfg.start_date, cfg.end_date)
    )
    print(f"Bars in window: {bars_in_window} / {len(bars['time'])}")
    print()

    # ---- 5. Collect unmapped keys (warn-only, not fatal) ----
    unmapped = collect_unmapped_keys(raw_config)
    if unmapped:
        print(f"WARNING: {len(unmapped)} unmapped config keys (not consumed by engine):")
        for k in unmapped:
            v = raw_config[k]
            print(f"  {k}: {v!r}")
        print()

    # ---- 6. Run backtest ----
    print("Running backtest...")
    result = run_backtest(bars, cfg, confluence_bars=None, collect_debug=False)
    trades = result["trades"]
    metrics = result["metrics"]
    print(f"Backtest complete: {metrics['trades']} trades")
    print()

    # ---- 7. Print detailed results ----
    closed_trades = [t for t in trades if t.get("reason") != "OPEN"]
    open_trades = [t for t in trades if t.get("reason") == "OPEN"]
    n_open = len(open_trades)

    # R-multiples of closed trades
    r_list = [t["r"] for t in closed_trades]

    wr = metrics["wr"]
    pf = metrics["pf"]
    dd_r = metrics["max_dd"]
    dd_pct = compute_dd_pct(r_list, cfg.risk_pct, cfg.symbol_vol_mult)

    gross_profit = metrics["gross_profit"]
    gross_loss = metrics["gross_loss"]
    net_profit = gross_profit - gross_loss
    expectancy = net_profit / metrics["trades"] if metrics["trades"] > 0 else 0.0

    print("=" * 60)
    print(f"{'Metric':<25} {'Engine':<15} {'TV Ref':<15} {'Delta':<10}")
    print("-" * 60)
    total_trades = metrics["trades"]
    print(f"{'Trades':<25} {total_trades:<15} {TV_REF['trades']:<15} "
          f"{total_trades - TV_REF['trades']:<+10}")
    print(f"{'Win Rate %':<25} {wr:<15.2f} {TV_REF['wr']:<15.2f} "
          f"{wr - TV_REF['wr']:<+10.2f}")
    print(f"{'Profit Factor':<25} {pf:<15.3f} {TV_REF['pf']:<15.3f} "
          f"{pf - TV_REF['pf']:<+.3f}")
    dd_str = f"{dd_pct:.2f}%" if dd_pct is not None else "N/A"
    print(f"{'Max DD %':<25} {dd_str:<15} {TV_REF['dd_pct']:<15.2f}%")
    print(f"{'Open trades':<25} {n_open:<15}")
    print(f"{'Expectancy (R)':<25} {expectancy:<15.4f}")
    print(f"{'Gross Profit R':<25} {gross_profit:<15.4f}")
    print(f"{'Gross Loss R':<25} {gross_loss:<15.4f}")
    print(f"{'Net Profit R':<25} {net_profit:<15.4f}")
    print(f"{'RR (config)':<25} {cfg.rr:<15.1f}")
    print("=" * 60)
    print()

    # ---- Long / Short split ----
    long_trades = [t for t in closed_trades if t["direction"] == "long"]
    short_trades = [t for t in closed_trades if t["direction"] == "short"]

    def split_stats(tlist):
        if not tlist:
            return {"count": 0, "wr": 0.0, "avg_r": 0.0}
        rs = [t["r"] for t in tlist]
        wins = sum(1 for r in rs if r > 0)
        return {
            "count": len(tlist),
            "wr": wins * 100.0 / len(tlist),
            "avg_r": sum(rs) / len(rs),
            "net_r": sum(rs),
        }

    long_s = split_stats(long_trades)
    short_s = split_stats(short_trades)

    print("--- Long / Short Split ---")
    print(f"{'Side':<8} {'Trades':<8} {'WR%':<8} {'Avg R':<8} {'Net R':<8}")
    print(f"{'Long':<8} {long_s['count']:<8} {long_s['wr']:<8.1f} "
          f"{long_s['avg_r']:<8.2f} {long_s['net_r']:<8.2f}")
    print(f"{'Short':<8} {short_s['count']:<8} {short_s['wr']:<8.1f} "
          f"{short_s['avg_r']:<8.2f} {short_s['net_r']:<8.2f}")
    print()

    # ---- Yearly counts ----
    yearly = {}
    for t in closed_trades:
        yr = datetime.fromtimestamp(bars["time"][t["bar"]] / 1000, tz=timezone.utc).year
        yearly[yr] = yearly.get(yr, 0) + 1
    print("--- Yearly Trade Counts ---")
    for yr in sorted(yearly):
        print(f"  {yr}: {yearly[yr]} trades")

    # Also add open trade to the count for total
    if open_trades:
        yr = datetime.fromtimestamp(bars["time"][open_trades[0]["bar"]] / 1000, tz=timezone.utc).year
        print(f"  {yr}: +{n_open} open trade(s)")
    print()

    # ---- Per-trade ledger ----
    all_trades = closed_trades + open_trades
    print(f"--- All Trades (n={len(all_trades)}) ---")
    for t in all_trades:
        ent_time = datetime.fromtimestamp(bars["time"][t["bar"]] / 1000, tz=timezone.utc)
        ext_time = datetime.fromtimestamp(bars["time"][t["exit_bar"]] / 1000, tz=timezone.utc)
        r_str = f"{t['r']:+.4f}" if not math.isnan(t["r"]) else "OPEN"
        print(f"  {ent_time:%Y-%m-%d %H:%M} {t['direction']:<5} "
              f"{t['module']:<10} fill={t['fill']:.1f} "
              f"exit={t['exit']:.1f} R={r_str} ({t['reason']})")
    print()

    # ---- 8. Write outputs ----
    # Trade ledger CSV
    csv_path = os.path.join(OUTPUT_DIR, "sot_ger40_prescreen_trades.csv")
    with open(csv_path, "w", newline="") as csvf:
        csvf.write("entry_time,exit_time,side,module,entry_price,exit_price,sl,tp,"
                    "risk,fill,bar,exit_bar,R,reason\n")
        for t in all_trades:
            ent_time = datetime.fromtimestamp(bars["time"][t["bar"]] / 1000, tz=timezone.utc)
            ext_time = datetime.fromtimestamp(bars["time"][t["exit_bar"]] / 1000, tz=timezone.utc)
            r_val = f"{t['r']:.6f}" if not math.isnan(t["r"]) else ""
            csvf.write(
                f"{ent_time:%Y-%m-%d %H:%M:%S},{ext_time:%Y-%m-%d %H:%M:%S},"
                f"{t['direction']},{t['module']},{t['fill']:.2f},{t['exit']:.2f},"
                f"{t['sl']:.2f},{t['tp']:.2f},{t['risk']:.6f},"
                f"{t['fill']:.2f},{t['bar']},{t['exit_bar']},{r_val},{t['reason']}\n"
            )

    print(f"Trade ledger written: {csv_path}")

    # Summary JSON
    summary = {
        "prescreen": "sot_v4.0_ger40_python",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "config_source": VERIFIED_CONFIG_PATH,
        "feed": {
            "path": feed_path,
            "provenance": feed_declared,
            "total_rows": len(bars["time"]),
            "date_range": {
                "start": datetime.fromtimestamp(bars["time"][0] / 1000, tz=timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(bars["time"][-1] / 1000, tz=timezone.utc).isoformat(),
            },
            "bars_in_window": bars_in_window,
        },
        "window_ms": {"start": start_ms, "end": end_ms},
        "engine_metrics": {
            "trades": total_trades,
            "closed_trades": len(closed_trades),
            "open_trades": n_open,
            "wr_pct": round(wr, 2),
            "pf": round(pf, 3),
            "max_dd_r": round(dd_r, 4),
            "max_dd_pct": round(dd_pct, 4) if dd_pct is not None else None,
            "expectancy_r": round(expectancy, 4),
            "gross_profit_r": round(gross_profit, 4),
            "gross_loss_r": round(gross_loss, 4),
            "net_profit_r": round(net_profit, 4),
            "rr_config": cfg.rr,
        },
        "tv_reference": {
            "trades": TV_REF["trades"],
            "wr_pct": TV_REF["wr"],
            "pf": TV_REF["pf"],
            "dd_pct": TV_REF["dd_pct"],
            "source": tv_res,
        },
        "deltas": {
            "trades": total_trades - TV_REF["trades"],
            "wr_pp": round(wr - TV_REF["wr"], 2),
            "pf": round(pf - TV_REF["pf"], 4),
        },
        "long_short": {
            "long": long_s,
            "short": short_s,
        },
        "yearly": {str(yr): cnt for yr, cnt in sorted(yearly.items())},
        "unmapped_keys_count": len(unmapped),
        "unmapped_keys": unmapped,
    }

    summary_path = os.path.join(OUTPUT_DIR, "sot_ger40_prescreen_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Summary written: {summary_path}")
    print()

    # ---- 9. Final verdict ----
    delta_tr = total_trades - TV_REF["trades"]
    delta_wr = wr - TV_REF["wr"]
    delta_pf = pf - TV_REF["pf"]

    print("=" * 60)
    print("VERDICT")
    print("=" * 60)

    consistent_tr = abs(delta_tr) <= 2
    consistent_wr = abs(delta_wr) <= 2.0

    result = {
        "trades_from_engine": total_trades,
        "wr_from_engine": round(wr, 2),
        "pf_from_engine": round(pf, 3),
        "dd_pct_from_engine": round(dd_pct, 2) if dd_pct is not None else None,
        "trades_from_tv": TV_REF["trades"],
        "wr_from_tv": TV_REF["wr"],
        "pf_from_tv": TV_REF["pf"],
        "dd_pct_from_tv": TV_REF["dd_pct"],
        "delta_trades": delta_tr,
        "delta_wr_pp": round(delta_wr, 2),
        "delta_pf": round(delta_pf, 4),
        "unmapped_keys_count": len(unmapped),
        "evidence_trades_csv": csv_path,
        "evidence_summary_json": summary_path,
    }

    print(f"  Engine:  {total_trades}tr / {wr:.2f}% / PF {pf:.3f} / DD {dd_str}")
    print(f"  TV ref:  {TV_REF['trades']}tr / {TV_REF['wr']}% / PF {TV_REF['pf']} / DD {TV_REF['dd_pct']}%")
    print(f"  Delta:   {delta_tr:+d}tr / {delta_wr:+.2f}pp WR / {delta_pf:+.4f} PF")
    print(f"  Unmapped keys: {len(unmapped)}")

    if consistent_tr and consistent_wr:
        print()
        print(">>> PRESCREEN_CONSISTENT <<<")
    else:
        print()
        print(">>> PRESCREEN_DIVERGENT <<<")
        print(f"  Reason: trades delta={delta_tr} (limit +/-2), "
              f"WR delta={delta_wr:+.2f}pp (limit +/-2.0pp)")

    print()
    return result


if __name__ == "__main__":
    result = main()
    # Print final acceptance line
    print(f"FINAL: {result['trades_from_engine']}tr/{result['wr_from_engine']:.2f}%/"
          f"{result['pf_from_engine']}/DD{result['dd_pct_from_engine']}% vs TV "
          f"{result['trades_from_tv']}tr/{result['wr_from_tv']}%/{result['pf_from_tv']}/"
          f"DD{result['dd_pct_from_tv']}%, "
          f"delta {result['delta_trades']:+d}tr/{result['delta_wr_pp']:+.2f}pp, "
          f"unmapped-keys {result['unmapped_keys_count']}")
    print(f"Evidence: {result['evidence_trades_csv']}")
    print(f"          {result['evidence_summary_json']}")
