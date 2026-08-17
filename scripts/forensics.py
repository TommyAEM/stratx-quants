#!/usr/bin/env python3
"""DE40 NEXTGEN forensics toolkit (phase 2).

Loads EA trade CSVs (15 base columns + optional 10 forensic f_* columns) or
Engine X prescreen ledgers. Optional date filter: --from --to (YYYY-MM-DD).

Commands:
  summary <csv>    core metrics + per-year + sides
  frontier <csv>   fixed-TP truncation grid via MFE
  splits <csv>     direction/weekday/hour/session tables
  diff <a> <b>     trade-level generation delta
  families <csv>   losing-cluster candidates via feature terciles (f_* columns)

Realized RR = mean winner / mean loser in R units.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

FEATS = ("f_atr_pct", "f_vwap_dist", "f_price_ema200", "f_range_w", "f_rel_vol",
         "f_disp", "f_h1_bias", "f_gap", "f_va_width", "f_poc_dist")


def _parse_dt(s):
    s = (s or "").strip()
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.weekday(), dt.hour
        except ValueError:
            continue
    if s.isdigit() and len(s) >= 9:
        dt = datetime.fromtimestamp(int(s), timezone.utc)
        return dt.weekday(), dt.hour
    return 0, 0


def _to_canon(s):
    s = (s or "").strip()
    if s.isdigit() and len(s) >= 9:
        dt = datetime.fromtimestamp(int(s), timezone.utc)
        return dt.strftime("%Y.%m.%d %H:%M:%S")
    return s


def _norm(row, schema):
    t = {}
    if schema == "engine":
        def f(k):
            try:
                return float(row.get(k, "") or 0)
            except ValueError:
                return 0.0
        t["R"] = f("R") if "R" in row else f("r")
        t["MFE_R"] = f("MFE_R")
        t["MAE_R"] = f("MAE_R")
        t["entry"] = f("entry_price")
        t["sl"] = f("sl")
        t["tp"] = f("tp")
        t["exit_price"] = f("exit_price")
        et = (row.get("entry_time") or "").strip()
        t["time_open"] = _to_canon(et)
        t["time_close"] = _to_canon(row.get("exit_time"))
        t["side"] = (row.get("side") or "").strip().lower()
        t["module"] = (row.get("module") or "").strip()
        t["session_bucket"] = "engine"
        wd, hr = _parse_dt(et)
        t["weekday"] = wd
        t["gmt_hour"] = hr
        t["feat"] = {}
        return t
    feat = {}
    for k in FEATS:
        try:
            feat[k] = float(row.get(k, "") or 0)
        except ValueError:
            feat[k] = 0.0
    t["feat"] = feat
    for k, conv in (("R", float), ("MFE_R", float), ("MAE_R", float),
                   ("entry", float), ("sl", float), ("tp", float),
                   ("exit_price", float), ("weekday", int), ("gmt_hour", int)):
        try:
            t[k] = conv(row.get(k, "") or 0)
        except ValueError:
            t[k] = 0.0 if conv is float else 0
    t["time_open"] = _to_canon(row.get("time_open"))
    t["time_close"] = _to_canon(row.get("time_close"))
    t["side"] = (row.get("side") or "").strip().lower()
    t["module"] = (row.get("module") or "").strip()
    t["session_bucket"] = (row.get("session_bucket") or "").strip()
    return t


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        schema = "engine" if "entry_time" in fields else "mt5"
        for r in rd:
            t = _norm(r, schema)
            if not t["time_open"]:
                continue
            rows.append(t)
    return rows


def _filter(rows, frm, to):
    out = []
    for t in rows:
        d = t["time_open"][:10].replace(".", "-")
        if frm and d < frm:
            continue
        if to and d > to:
            continue
        out.append(t)
    return out


def _pf(rows):
    gp = sum(t["R"] for t in rows if t["R"] > 0)
    gl = -sum(t["R"] for t in rows if t["R"] < 0)
    return (gp / gl) if gl > 0 else float("inf")


def _years(rows):
    out = defaultdict(list)
    for t in rows:
        out[t["time_open"][:4]].append(t)
    return dict(sorted(out.items()))


def _dd(rows):
    eq = peak = dd = 0.0
    for t in rows:
        eq += t["R"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


def _consec(rows):
    mx = c = 0
    for t in rows:
        c = c + 1 if t["R"] <= 0 else 0
        mx = max(mx, c)
    return mx


def _realized_rr(rows):
    w = [t["R"] for t in rows if t["R"] > 0]
    l = [-t["R"] for t in rows if t["R"] < 0]
    if not w or not l:
        return None
    return (sum(w) / len(w)) / (sum(l) / len(l))


def summary(rows):
    n = len(rows)
    if n == 0:
        return {"trades": 0}
    wins = [t for t in rows if t["R"] > 0]
    wr = 100.0 * len(wins) / n
    net = sum(t["R"] for t in rows)
    span_days = None
    try:
        f0 = datetime.strptime(rows[0]["time_open"][:16], "%Y.%m.%d %H:%M")
        f1 = datetime.strptime(rows[-1]["time_open"][:16], "%Y.%m.%d %H:%M")
        span_days = max(1.0, (f1 - f0).days)
    except Exception:
        span_days = None
    tpy = n * 365.0 / span_days if span_days else None
    per_year = {y: {"trades": len(v), "wr": round(100.0 * sum(1 for t in v if t["R"] > 0) / len(v), 2),
                    "net_r": round(sum(t["R"] for t in v), 2), "pf": round(_pf(v), 3),
                    "realized_rr": round(_realized_rr(v) or 0, 3)}
                for y, v in _years(rows).items()}
    sides = {}
    for s in ("buy", "sell", "long", "short"):
        v = [t for t in rows if t["side"] == s]
        if v:
            sides[s] = {"trades": len(v), "wr": round(100.0 * sum(1 for t in v if t["R"] > 0) / len(v), 2),
                        "net_r": round(sum(t["R"] for t in v), 2),
                        "realized_rr": round(_realized_rr(v) or 0, 3)}
    return {
        "trades": n,
        "wr_pct": round(wr, 2),
        "pf": round(_pf(rows), 3),
        "net_r": round(net, 2),
        "expectancy_r": round(net / n, 3),
        "realized_rr": round(_realized_rr(rows) or 0, 3),
        "dd_r": round(_dd(rows), 2),
        "max_consec_loss": _consec(rows),
        "trades_per_year": round(tpy, 1) if tpy else None,
        "sides": sides,
        "per_year": per_year,
    }


def frontier(rows, tps=(0.7, 0.8, 1.0, 1.2, 1.5)):
    out = {}
    for tp in tps:
        rs = [tp if t["MFE_R"] >= tp else t["R"] for t in rows]
        n = len(rs)
        if n == 0:
            continue
        w = [r for r in rs if r > 0]
        l = [-r for r in rs if r < 0]
        rr = (sum(w) / len(w)) / (sum(l) / len(l)) if w and l else None
        out[str(tp)] = {"trades": n, "wr_pct": round(100.0 * len(w) / n, 2),
                        "net_r": round(sum(rs), 2),
                        "realized_rr": round(rr or 0, 3)}
    return out


def splits(rows):
    def table(keyfn):
        g = defaultdict(list)
        for t in rows:
            g[keyfn(t)].append(t)
        return {str(k): {"trades": len(v), "wr": round(100.0 * sum(1 for t in v if t["R"] > 0) / len(v), 2),
                         "net_r": round(sum(t["R"] for t in v), 2),
                         "standalone_positive": sum(t["R"] for t in v) > 0}
                for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))}
    return {
        "side": table(lambda t: t["side"]),
        "weekday": table(lambda t: t["weekday"]),
        "hour_bucket": table(lambda t: f"{t['gmt_hour'] // 3 * 3:02d}-{t['gmt_hour'] // 3 * 3 + 3:02d}"),
        "session_bucket": table(lambda t: t["session_bucket"]),
    }


def diff(parent, child):
    pk = {(t["time_open"], t["side"]): t for t in parent}
    ck = {(t["time_open"], t["side"]): t for t in child}
    removed = [pk[k] for k in pk.keys() - ck.keys()]
    added = [ck[k] for k in ck.keys() - pk.keys()]
    kept = [ck[k] for k in ck.keys() & pk.keys()]

    def wl(v):
        return (sum(1 for t in v if t["R"] <= 0), sum(1 for t in v if t["R"] > 0))
    rl, rw = wl(removed)
    al, aw = wl(added)
    return {
        "parent_trades": len(parent), "child_trades": len(child),
        "retained": len(kept), "retention_pct": round(100.0 * len(kept) / len(parent), 1) if parent else None,
        "removed": len(removed), "removed_losers": rl, "removed_winners": rw,
        "removed_net_r": round(sum(t["R"] for t in removed), 2),
        "added": len(added), "added_losers": al, "added_winners": aw,
        "added_net_r": round(sum(t["R"] for t in added), 2),
        "parent_net_r": round(sum(t["R"] for t in parent), 2),
        "child_net_r": round(sum(t["R"] for t in child), 2),
    }


def families(rows, min_n=5):
    """Losing-cluster candidates: tercile splits over each f_* feature.
    For each band report n, WR, net R, loser count and loss share, plus the
    matched winners in the same band (same population, so 'comparable')."""
    losers = [t for t in rows if t["R"] <= 0]
    winners = [t for t in rows if t["R"] > 0]
    if not losers or not winners:
        return []
    out = []
    for k in FEATS:
        vals = sorted(t["feat"][k] for t in rows)
        if not vals or all(v == vals[0] for v in vals):
            continue
        t1 = vals[len(vals) // 3]
        t2 = vals[2 * len(vals) // 3]
        for lo, hi, label in ((None, t1, "low"), (t1, t2, "mid"), (t2, None, "high")):
            def inb(t):
                v = t["feat"][k]
                return (lo is None or v >= lo) and (hi is None or v < hi)
            sub = [t for t in rows if inb(t)]
            n = len(sub)
            if n < min_n:
                continue
            lsub = [t for t in losers if inb(t)]
            wsub = [t for t in winners if inb(t)]
            out.append({
                "feature": k, "band": label, "n": n,
                "wr": round(100.0 * len(wsub) / n, 1),
                "net_r": round(sum(t["R"] for t in sub), 2),
                "losers": len(lsub), "winners": len(wsub),
                "loss_share": round(100.0 * len(lsub) / len(losers), 1),
                "loser_mae": round(sum(t["MAE_R"] for t in lsub) / len(lsub), 2) if lsub else 0,
                "winner_mfe": round(sum(t["MFE_R"] for t in wsub) / len(wsub), 2) if wsub else 0,
            })
    out.sort(key=lambda d: d["net_r"])
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "summary"
    frm = to = None
    rest = []
    i = 2
    while i < len(argv):
        if argv[i] == "--from":
            frm = argv[i + 1]; i += 2
        elif argv[i] == "--to":
            to = argv[i + 1]; i += 2
        else:
            rest.append(argv[i]); i += 1
    rows = _filter(load(rest[0]), frm, to) if rest else []
    if cmd == "summary":
        print(json.dumps(summary(rows), indent=2))
    elif cmd == "frontier":
        print(json.dumps(frontier(rows), indent=2))
    elif cmd == "splits":
        print(json.dumps(splits(rows), indent=2))
    elif cmd == "diff":
        rows2 = _filter(load(rest[1]), frm, to) if len(rest) > 1 else []
        print(json.dumps(diff(rows, rows2), indent=2))
    elif cmd == "families":
        print(json.dumps(families(rows), indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
