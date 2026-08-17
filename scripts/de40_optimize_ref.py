#!/usr/bin/env python3
"""
DE40 X1 wide-range genetic optimizer (PU Prime, PID-scoped, fail-closed).

Follows the proven StratX pipeline:
  * 5-field .set format  Key=Value||Start||Step||Stop||Flag  (Y=swept, N=fixed)
  * bare .set filename in ExpertParameters, staged in MQL5/Profiles/Tester
  * Optimization=2 (GA), OptimizationCriterion=6 (Custom max = OnTester bands)
  * Model=1 (1-min OHLC) for GA speed; band passers re-confirmed on Model=4
  * ZERO kill-by-name: only ever terminates its own launched PID

Usage:
  python de40_optimize.py ga  <tag> <from> <to> [--timeout 7200]
  python de40_optimize.py top <tag>                 # parse finished XML
"""
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PU_PRIME_EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
PU_PRIME_DATA = Path(r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075")
SET_DIR = PU_PRIME_DATA / "MQL5" / "Profiles" / "Tester"
PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "EVIDENCE" / "OPT"
SYMBOL = "GER40.s"
EXPERT = "DE40_X1.ex5"

MODULE_MASKS = {"A": 1, "B": 2, "C": 4, "D": 8, "E": 16, "F": 32, "G": 64, "H": 128}

# ---- wide parameter space -------------------------------------------------
# fixed base per module (never swept)
def base_params(module: str) -> dict:
    return {
        "InpModuleMask": MODULE_MASKS[module],
        "InpServerUTC": 3,
        "InpMagic": 446404093,
        "InpMaxSpreadPts": 300,
        "InpRiskLevel": 1,
        "InpORAnchorGMT": 8,
        "InpORAnchorMin": 0,
        "InpTPMode": 3,
        "InpATRPeriod": 14,
        "InpStopLossDay": 0,
        "InpDDCutPct": 12.0,
        "InpColdStartSec": 0,
        "InpNewsAvoid": 0,
        "InpShowDashboard": 0,
        "InpConfMode": 0,
        "InpOptYears": 2.0,
        "InpOptMinTpy": 21.0,
    }

# swept dimensions: name -> (start, step, stop)
FBO_SPACE = {
    # FBO core geometry
    "InpMinBreakATR":    (0.5, 0.25, 2.0),
    "InpMaxBreakATR":    (1.0, 0.5, 3.0),
    "InpMaxBarsOutside": (4, 2, 12),
    "InpDispBodyATR":    (0.5, 0.25, 2.0),
    "InpMaxBarsToDisp":  (6, 3, 18),
    "InpEntryMode":      (0, 1, 4),
    "InpFillFraction":   (0.3, 0.1, 0.7),
    "InpRetracePct":     (0.3, 0.1, 0.7),
    "InpMaxRetraceBars": (8, 4, 32),
    # stops and targets
    "InpSLMode":         (0, 1, 2),
    "InpSL_BufferATR":   (0.0, 0.1, 0.5),
    "InpSL_ATR":         (1.0, 0.25, 2.5),
    "InpTP_RR":          (0.7, 0.1, 2.0),
    "InpTimeStopMin":    (0, 60, 360),
    # FBL exit management
    "InpEnablePartialClose": (0, 1, 1),
    "InpPartialPercent":     (30, 10, 70),
    "InpPartialTargetR":     (0.5, 0.25, 1.5),
    "InpMoveRunnerToBE":     (0, 1, 1),
    "InpEnableATRTrail":     (0, 1, 1),
    "InpATRTrailMultiplier": (1.0, 0.5, 3.0),
    "InpRunnerMaxR":         (2.0, 1.0, 5.0),
    # volatility filters
    "InpMinATR":         (3.0, 1.0, 8.0),
    "InpMaxATR":         (500.0, 100.0, 900.0),
    # entry-quality gate
    "InpUseNativeConf":  (0, 1, 2),
    "InpNcTrendPeriod":  (50, 50, 300),
    # sessions and frequency
    "InpSessionMask":    (1, 1, 15),
    "InpMaxTradesDay":   (2, 1, 6),
}

GLK_SPACE = {
    # EMA structure
    "InpGlkFast":        (5, 2, 21),
    "InpGlkMed":         (13, 4, 55),
    "InpGlkSlow":        (34, 8, 144),
    "InpGlkPersist":     (1, 1, 8),
    "InpGlkSepMinATR":   (0.05, 0.05, 0.5),
    "InpGlkSepMaxATR":   (0.5, 0.5, 4.0),
    "InpGlkSlopeLb":     (2, 1, 12),
    "InpGlkSlopeMin":    (-0.1, 0.05, 0.2),
    # pullback geometry
    "InpGlkMinPullATR":  (0.1, 0.1, 1.0),
    "InpGlkMaxPullBars": (4, 2, 24),
    "InpGlkInvalATR":    (0.2, 0.2, 2.0),
    "InpGlkSLBufATR":    (0.0, 0.1, 0.8),
    "InpGlkMaxSLATR":    (1.5, 0.5, 6.0),
    "InpGlkTP_RR":       (0.7, 0.1, 2.5),
    "InpGlkStartGMT":    (7, 1, 10),
    "InpGlkEndGMT":      (12, 1, 20),
    "InpGlkAllowShort":  (0, 1, 1),
    # exits (shared FBL)
    "InpEnablePartialClose": (0, 1, 1),
    "InpPartialPercent":     (30, 10, 70),
    "InpPartialTargetR":     (0.5, 0.25, 1.5),
    "InpTimeStopMin":        (0, 60, 360),
    # gate / filters / frequency
    "InpUseNativeConf":  (0, 1, 2),
    "InpNcTrendPeriod":  (50, 50, 300),
    "InpMinATR":         (3.0, 1.0, 8.0),
    "InpMaxATR":         (500.0, 100.0, 900.0),
    "InpMaxTradesDay":   (2, 1, 6),
}

VWAP_SPACE = {
    # session anchor and structure
    "InpVwapStartGMT":   (6, 1, 9),
    "InpVwapEndGMT":     (12, 1, 20),
    "InpVwapStructLb":   (4, 2, 24),
    "InpVwapSlopeBars":  (10, 10, 90),
    # pullback geometry
    "InpVwapBandATR":    (0.1, 0.1, 1.5),
    "InpVwapBreakATR":   (0.3, 0.2, 2.5),
    "InpVwapMaxPullATR": (1.0, 0.5, 5.0),
    "InpVwapMaxPullBars": (4, 2, 24),
    "InpVwapSLBufATR":   (0.0, 0.1, 0.8),
    "InpVwapMaxSLATR":   (1.5, 0.5, 6.0),
    "InpVwapTP_RR":      (0.7, 0.1, 2.5),
    "InpVwapMinRoomR":   (0.5, 0.5, 3.0),
    "InpVwapAllowShort": (0, 1, 1),
    # exits (shared FBL)
    "InpEnablePartialClose": (0, 1, 1),
    "InpPartialPercent":     (30, 10, 70),
    "InpPartialTargetR":     (0.5, 0.25, 1.5),
    "InpTimeStopMin":        (0, 60, 360),
    # gate / filters / frequency
    "InpUseNativeConf":  (0, 1, 2),
    "InpNcTrendPeriod":  (50, 50, 300),
    "InpMinATR":         (3.0, 1.0, 8.0),
    "InpMaxATR":         (500.0, 100.0, 900.0),
    "InpSessionMask":    (1, 1, 15),
    "InpMaxTradesDay":   (2, 1, 6),
}

SPACE = FBO_SPACE  # default; build_set selects per module


def space_for(module: str):
    if module in ("G",):
        return GLK_SPACE
    if module in ("H",):
        return VWAP_SPACE
    return FBO_SPACE


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def build_set(tag: str, module: str):
    base = base_params(module)
    space = space_for(module)
    lines = [f"; DE40 wide GA {tag} - {datetime.now():%Y-%m-%d %H:%M}"]
    combos = 1
    swept = []
    for k, v in base.items():
        s = fmt(v)
        lines.append(f"{k}={s}||{s}||{s}||{s}||N")
    for k, (start, step, stop) in space.items():
        cur = fmt(base.get(k, "")) if k in base else ""
        # current value: midpoint-ish default; any legal value works for GA
        n = int(round((stop - start) / step)) + 1
        combos *= n
        swept.append(k)
        lines.append(f"{k}={cur or start}||{start}||{step}||{stop}||Y")
    return "\n".join(lines) + "\n", swept, combos


def terminal_processes():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
         "Select-Object ProcessId,ExecutablePath | ConvertTo-Json"],
        capture_output=True, text=True, check=True).stdout.strip()
    if not out:
        return []
    import json
    data = json.loads(out)
    return data if isinstance(data, list) else [data]


def assert_tester_free():
    procs = terminal_processes()
    mine = [p for p in procs
            if (p.get("ExecutablePath") or "").lower() == PU_PRIME_EXE.lower()]
    if mine:
        raise SystemExit(
            f"ABORT: PU Prime already running (PIDs {[p['ProcessId'] for p in mine]}). "
            f"Never killing pre-existing terminals.")


def write_ini(ini_path: Path, report_name: str, set_name: str,
              from_date: str, to_date: str):
    ini = f"""[Common]
ProxyEnable=0
AutoUpdate=0

[Tester]
Expert={EXPERT}
Symbol={SYMBOL}
Period=M15
FromDate={from_date}
ToDate={to_date}
Deposit=10000
Currency=USD
Leverage=100
Model=1
Optimization=2
OptimizationCriterion=6
Forward=0
ExecutionDelay=0
Report={report_name}.xml
ReplaceReport=1
ShutdownTerminal=1
ExpertParameters={set_name}.set

[Charts]
"""
    ini_path.write_text(ini, encoding="utf-8")


def parse_opt_xml(path: Path):
    """Parse optimization XML (Office SpreadsheetML). Returns (rows, header).
    Columns: pass, result, profit, payoff, pf, recovery, sharpe, custom,
    dd, trades, then optimized parameter values in .set Y-row order."""
    ns = {"x": "urn:schemas-microsoft-com:office:spreadsheet"}
    rows = ET.parse(str(path)).getroot().findall(".//x:Row", ns)
    if not rows:
        return [], []
    header = [c.text for c in rows[0].findall("x:Cell/x:Data", ns)]
    out = []
    for row in rows[1:]:
        vals = [c.text for c in row.findall("x:Cell/x:Data", ns)]
        if len(vals) < 10:
            continue
        try:
            out.append({
                "pass": int(vals[0]),
                "result": float(vals[1] or 0),
                "profit": float(vals[2] or 0),
                "payoff": float(vals[3] or 0),
                "pf": float(vals[4] or 0),
                "recovery": float(vals[5] or 0),
                "sharpe": float(vals[6] or 0),
                "custom": float(vals[7] or 0),
                "dd": float(vals[8] or 0),
                "trades": int(vals[9] or 0),
                "params": vals[10:],
            })
        except (ValueError, TypeError):
            continue
    return out, header


def swept_names(module: str):
    """Y-row order as emitted by build_set."""
    return list(space_for(module).keys())


def reconstruct(param_values, y_names, module: str):
    p = dict(base_params(module))
    for i, name in enumerate(y_names):
        if i >= len(param_values) or param_values[i] is None:
            continue
        v = param_values[i]
        if isinstance(v, str) and v.strip().lower() in ("true", "false"):
            p[name] = v.strip().lower() == "true"
        else:
            try:
                f = float(v)
            except ValueError:
                continue
            if isinstance(p.get(name), bool):
                p[name] = bool(int(f))
            else:
                p[name] = int(f) if f == int(f) else f
    return p


def cmd_ga(args):
    tag, from_date, to_date = args[0], args[1], args[2]
    timeout = 7200
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    module = tag.split("_")[0]
    if module not in MODULE_MASKS:
        raise SystemExit(f"tag must start with module letter A-H, got {tag}")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    content, swept, combos = build_set(tag, module)
    print(f"swept dimensions: {len(swept)}, naive grid: {combos:.3e}")
    set_path = SET_DIR / f"{tag}.set"
    SET_DIR.mkdir(parents=True, exist_ok=True)
    set_path.write_text(content, encoding="utf-8")
    shutil.copy2(set_path, EVIDENCE / f"{tag}.set")

    report_name = f"DE40_{tag}"
    ini_path = PU_PRIME_DATA / f"{report_name}.ini"
    write_ini(ini_path, report_name, tag, from_date, to_date)
    shutil.copy2(ini_path, EVIDENCE / f"{report_name}.ini")

    xml_out = PU_PRIME_DATA / f"{report_name}.xml"
    if xml_out.exists():
        xml_out.unlink()

    assert_tester_free()
    started = datetime.now()
    print(f"launching GA: {ini_path}")
    proc = subprocess.Popen([PU_PRIME_EXE, f"/config:{ini_path}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"PID {proc.pid} started {started.isoformat()}")
    meta = {"tag": tag, "pid": proc.pid, "started": str(started),
            "from": from_date, "to": to_date, "swept": swept}
    (EVIDENCE / f"{tag}_meta.json").write_text(
        str(meta).replace("'", '"'), encoding="utf-8")

    t0 = time.time()
    while proc.poll() is None:
        if time.time() - t0 > timeout:
            print(f"TIMEOUT after {timeout}s — killing own PID {proc.pid} only")
            proc.kill()
            proc.wait(timeout=60)
            raise SystemExit("GA timed out")
        time.sleep(15)
    ended = datetime.now()
    print(f"exit code {proc.returncode} after {int(time.time()-t0)}s, ended {ended}")

    if xml_out.exists():
        dst = EVIDENCE / f"{report_name}.xml"
        shutil.copy2(xml_out, dst)
        print(f"optimization XML -> {dst} ({dst.stat().st_size} bytes)")
        cmd_top([tag])
    else:
        print("NO XML REPORT — check terminal journal for 'optimization settings error'")
        journal = PU_PRIME_DATA / "logs" / f"{ended:%Y%m%d}.log"
        if journal.exists():
            tail = journal.read_text(errors="replace").splitlines()[-40:]
            print("\n".join(l for l in tail if "ptim" in l or "rror" in l or "Tester" in l)[-3000:])
        raise SystemExit(1)


def cmd_top(args):
    tag = args[0]
    xml = EVIDENCE / f"DE40_{tag}.xml"
    if not xml.exists():
        raise SystemExit(f"missing {xml}")
    module = tag.split("_")[0]
    rows, header = parse_opt_xml(xml)
    if not rows:
        raise SystemExit("no rows parsed from XML")
    rows.sort(key=lambda r: r["custom"], reverse=True)
    y = swept_names(module)
    print(f"{len(rows)} passes | header: {header[:12]}...")
    nonzero = [r for r in rows if r["custom"] > 0]
    print(f"band-passing passes (custom>0): {len(nonzero)}")
    for i, r in enumerate(rows[:15]):
        print(f"#{i+1} pass={r['pass']} score={r['custom']:.2f} profit={r['profit']:.2f} "
              f"pf={r['pf']:.2f} dd={r['dd']:.2f}% trades={r['trades']} payoff={r['payoff']:.2f}")
        p = reconstruct(r["params"], y, module)
        shown = {k: p[k] for k in y if k in p}
        print(f"    {shown}")


def cmd_confirm(args):
    """Materialize top-N band-passing passes as fixed .set files for
    real-tick confirmation via de40_safe_runner.py."""
    tag = args[0]
    n = int(args[1]) if len(args) > 1 else 5
    xml = EVIDENCE / f"DE40_{tag}.xml"
    if not xml.exists():
        raise SystemExit(f"missing {xml}")
    module = tag.split("_")[0]
    rows, _ = parse_opt_xml(xml)
    rows.sort(key=lambda r: r["custom"], reverse=True)
    y = swept_names(module)
    preset_dir = PROJECT / "PRESETS"
    written = []
    for i, r in enumerate([x for x in rows if x["custom"] > 0][:n]):
        p = reconstruct(r["params"], y, module)
        name = f"DE40_{tag}_TOP{i+1}"
        lines = []
        for k, v in p.items():
            if isinstance(v, bool):
                v = "true" if v else "false"
            lines.append(f"{k}={v}")
        (preset_dir / f"{name}.set").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append((name, r["custom"], r["profit"], r["pf"], r["trades"]))
        print(f"wrote {name}.set  score={r['custom']:.2f} profit={r['profit']:.2f} "
              f"pf={r['pf']:.2f} trades={r['trades']}")
    if not written:
        print("NO band-passing passes in this optimization.")
    else:
        print("\nConfirm each on REAL ticks, e.g.:")
        for name, *_ in written:
            print(f"  python de40_safe_runner.py test {name}_FIT {name}.set 2023.01.01 2024.12.31")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "ga":
        cmd_ga(sys.argv[2:])
    elif sys.argv[1] == "top":
        cmd_top(sys.argv[2:])
    elif sys.argv[1] == "confirm":
        cmd_confirm(sys.argv[2:])
    else:
        print(__doc__)
