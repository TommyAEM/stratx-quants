#!/usr/bin/env python3
"""
DE40 X1 SAFE RUNNER (takeover edition)
======================================
Replaces de40_test_runner.py. Hard safety rules:

  * NEVER terminates processes by name or by executable path.
  * Only ever terminates the exact PID it launched itself.
  * Fails closed if any identity assertion fails.
  * Never touches the Vantage installation.

Subcommands:
  identity            Visible launch of PU Prime via MT5 API, verify account
                      company / server / masked login / data-dir hash, then
                      detach API (terminal stays open).
  diag                Fresh tester diagnostic (GER40.s M15 2026.07.01-07.31,
                      real ticks Model=4, one FBO module, unique report).
  test <id> <set> <from> <to>   PID-scoped single backtest.
  opt <id> <set> <from> <to> [passes]  Headless genetic optimization.
  sync                Ensure GER40.s M15 history is present via MT5 API.

All evidence is written to <project>/EVIDENCE/RUNS/<run_id>/
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ---------------- Canonical identity (asserted before every test) ----------
# ---------------- Terminal profiles (env-selectable) ------------------------
# DE40_TERMINAL=puprime (default, data-rich research) | vantage (VantageResearch)
_TERMINAL = os.environ.get("DE40_TERMINAL", "puprime").strip().lower()

_PROFILES = {
    "puprime": {
        "exe": r"C:\Program Files\MetaTrader 5\terminal64.exe",
        "data": r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075",
        "company": "PU Prime Ltd",
        "server": "PUPrime-Demo",
        "account_ending": "7739",
        "symbol": "GER40.s",
        "assert_company": True,
    },
    "vantage": {
        "exe": r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe",
        "data": r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\E07A066BDB2C10AD677A715C4DEC32A2",
        "company": None,  # logged, not asserted
        "server": "VantageMarkets-Demo",
        "account_ending": None,  # logged, not asserted
        "symbol": "GER40",
        "assert_company": False,
    },
}
if _TERMINAL not in _PROFILES:
    raise SystemExit(f"DE40_TERMINAL must be one of {sorted(_PROFILES)}, got '{_TERMINAL}'")
_PROF = _PROFILES[_TERMINAL]

PU_PRIME_EXE = _PROF["exe"]
PU_PRIME_DATA = _PROF["data"]
VANTAGE_EXE = r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe"

EXPECTED_COMPANY = _PROF["company"]
EXPECTED_SERVER = _PROF["server"]
EXPECTED_ACCOUNT_ENDING = _PROF["account_ending"]
EXPECTED_DATA_HASH = Path(_PROF["data"]).name
EXPECTED_SYMBOL = _PROF["symbol"]

EXPERT_NAME = os.environ.get("DE40_EXPERT", "DE40_X1").strip() or "DE40_X1"
PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "evidence"
PRESETS = PROJECT / "set"
TESTER_PROFILES = Path(PU_PRIME_DATA) / "MQL5" / "Profiles" / "Tester"

# Model values for [Tester] Model= (MT5 config ini):
#   0 = Every tick (generated)     1 = 1 minute OHLC (generated)
#   2 = 4 minutes OHLC             3 = 12 minutes OHLC
#   4 = Every tick based on REAL ticks   <-- only acceptable model
MODEL_REAL_TICKS = 4


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class FatalError(RuntimeError):
    pass


def now():
    return datetime.now()


def log(msg):
    print(f"[{now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- Process inventory (read-only) ----------------------------

def terminal_processes():
    """Return list of dicts for every running terminal64.exe. Read-only."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
         "Select-Object ProcessId,ExecutablePath,CreationDate | ConvertTo-Json"],
        capture_output=True, text=True, check=True).stdout.strip()
    if not out:
        return []
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    return data


def snapshot_vantage():
    """PIDs of Vantage processes (by exact exe path). Used before/after only."""
    return [p["ProcessId"] for p in terminal_processes()
            if (p.get("ExecutablePath") or "").lower() == VANTAGE_EXE.lower()]


def snapshot_puprime():
    return [p["ProcessId"] for p in terminal_processes()
            if (p.get("ExecutablePath") or "").lower() == PU_PRIME_EXE.lower()]


def assert_vantage_alive(before_pids, stage):
    after = snapshot_vantage()
    missing = [p for p in before_pids if p not in after]
    if missing:
        # External Vantage PID churn (user restart / crash) is NOT caused by this runner:
        # stop_pid() is PID-scoped to the PU Prime process we launched. Demote to a warning
        # so an unrelated live-Vantage restart does not block the whole research batch.
        log(f"WARNING: Vantage PIDs {missing} disappeared at stage '{stage}' "
            f"(external churn, not this runner — continuing)")
    else:
        log(f"Vantage OK at '{stage}': PIDs {after}")


# ---------------- Identity assertions ---------------------------------------

def read_text_any(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    return raw.decode("utf-8", errors="replace")


def verify_origin_mapping():
    """Data dir must declare PU Prime executable as its origin."""
    origin_file = Path(PU_PRIME_DATA) / "origin.txt"
    if not origin_file.exists():
        raise FatalError(f"origin.txt missing: {origin_file}")
    origin = read_text_any(origin_file).strip().lstrip("\ufeff").strip("\x00").strip()
    if Path(origin) != Path(PU_PRIME_EXE).parent:
        raise FatalError(f"origin.txt says '{origin}', expected PU Prime folder")
    log(f"origin.txt OK: {origin}")


def mt5_identity_check(visible=True, settle=45):
    """
    Launch PU Prime visibly via the MetaTrader5 API and verify identity.
    Returns dict with evidence. Terminal stays open; API detaches.
    """
    import MetaTrader5 as mt5

    vantage_before = snapshot_vantage()
    puprime_before = snapshot_puprime()
    if puprime_before:
        raise FatalError(f"PU Prime already running (PIDs {puprime_before}). "
                         f"I will not kill it — close it manually or let it finish.")

    log(f"Launching PU Prime visibly: {PU_PRIME_EXE}")
    if not mt5.initialize(path=PU_PRIME_EXE):
        raise FatalError(f"mt5.initialize failed: {mt5.last_error()}")

    evidence = {"launched_at": now().isoformat()}
    try:
        term = acc = None
        deadline = time.time() + settle
        while time.time() < deadline:
            term = mt5.terminal_info()
            acc = mt5.account_info()
            if term and acc and getattr(term, "connected", False):
                break
            time.sleep(2)
        if not term or not acc:
            raise FatalError(f"Terminal did not connect within {settle}s: {mt5.last_error()}")

        evidence.update({
            "terminal_build": term.build,
            "terminal_connected": bool(term.connected),
            "data_path": term.data_path,
            "company": acc.company,
            "server": acc.server,
            "login_masked": "*****" + str(acc.login)[-4:],
            "trade_allowed": bool(term.trade_allowed),
        })

        # Hard assertions — fail closed (company/login only when profile asserts)
        if _PROF["assert_company"]:
            if acc.company != EXPECTED_COMPANY:
                raise FatalError(f"Company mismatch: got '{acc.company}'")
            if not str(acc.login).endswith(EXPECTED_ACCOUNT_ENDING):
                raise FatalError(f"Account mismatch: got '*****{str(acc.login)[-4:]}'")
        if acc.server != EXPECTED_SERVER:
            raise FatalError(f"Server mismatch: got '{acc.server}'")
        if EXPECTED_DATA_HASH not in term.data_path:
            raise FatalError(f"Data dir mismatch: got '{term.data_path}'")

        # Symbol check
        spec = mt5.symbol_info(EXPECTED_SYMBOL)
        if spec is None:
            mt5.symbol_select(EXPECTED_SYMBOL, True)
            spec = mt5.symbol_info(EXPECTED_SYMBOL)
        if spec is None:
            raise FatalError(f"Symbol {EXPECTED_SYMBOL} not found on this account")
        mt5.symbol_select(EXPECTED_SYMBOL, True)
        rates = mt5.copy_rates_from_pos(EXPECTED_SYMBOL, mt5.TIMEFRAME_M15, 0, 5000)
        bars = 0 if rates is None else len(rates)
        first_bar = last_bar = None
        if bars:
            import datetime as dt
            first_bar = dt.datetime.fromtimestamp(int(rates[0][0])).isoformat()
            last_bar = dt.datetime.fromtimestamp(int(rates[-1][0])).isoformat()
        ticks = mt5.copy_ticks_from(EXPECTED_SYMBOL,
                                    int(datetime(2026, 7, 1).timestamp()),
                                    int(datetime(2026, 7, 31).timestamp()),
                                    1_000_000)
        evidence.update({
            "symbol": EXPECTED_SYMBOL,
            "symbol_visible": bool(spec.visible),
            "trade_mode": spec.trade_mode,
            "digits": spec.digits,
            "point": spec.point,
            "spread_points": spec.spread,
            "volume_min": spec.volume_min,
            "m15_bars_in_last_5000_window": bars,
            "m15_first_bar": first_bar,
            "m15_last_bar": last_bar,
            "july2026_ticks_available": len(ticks) if ticks is not None else 0,
        })
        assert_vantage_alive(vantage_before, "identity-check")
        log("ALL IDENTITY ASSERTIONS PASSED")
    finally:
        mt5.shutdown()  # detach API only; terminal keeps running
    return evidence


def stop_pid(pid, why):
    """Terminate ONE specific PID that this runner launched. Nothing else."""
    log(f"Stopping PID {pid} ({why}) — PID-scoped, nothing else touched")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)


# ---------------- Report handling -------------------------------------------

def archive_stale_reports():
    """Move pre-existing DE40_* reports in the data dir to STALE_REPORTS."""
    stale_dir = Path(PU_PRIME_DATA) / "STALE_REPORTS"
    moved = []
    for f in Path(PU_PRIME_DATA).glob("DE40_*.htm*"):
        stale_dir.mkdir(exist_ok=True)
        dst = stale_dir / f.name
        n = 1
        while dst.exists():
            dst = stale_dir / f"{f.stem}_{n}{f.suffix}"
            n += 1
        shutil.move(str(f), str(dst))
        moved.append(str(dst))
    for f in Path(PU_PRIME_DATA).glob("DE40_*.ini"):
        stale_dir.mkdir(exist_ok=True)
        shutil.move(str(f), stale_dir / f.name)
        moved.append(str(stale_dir / f.name))
    if moved:
        log(f"Archived {len(moved)} stale artefacts -> {stale_dir}")
    return moved


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[\s\xa0]+", " ", text)


def parse_report(report_path):
    """Extract the stats table from a Strategy Tester htm report."""
    text = strip_html(read_text_any(report_path))
    stats = {"_raw_header": text[:600]}
    patterns = {
        "broker_header": r"(PUPrime-Demo|VantageMarkets-Demo)\s*\(Build\s*(\d+)\)",
        "expert": r"Expert:\s*([\w\\\.]+)",
        "symbol": r"Symbol:\s*([\w\.]+)",
        "period": r"M15\s*\((\d{4}\.\d{2}\.\d{2})\s*-\s*(\d{4}\.\d{2}\.\d{2})\)",
        "net_profit": r"Total Net Profit\s+(-?[\d\s]+\.\d{2})",
        "gross_profit": r"Gross Profit\s+([\d\s]+\.\d{2})",
        "gross_loss": r"Gross Loss\s+(-?[\d\s]+\.\d{2})",
        "profit_factor": r"Profit Factor\s+(-?[\d\.]+)",
        "expected_payoff": r"Expected Payoff\s+(-?[\d\.]+)",
        "recovery_factor": r"Recovery Factor\s+(-?[\d\.]+)",
        "sharpe": r"Sharpe Ratio\s+(-?[\d\.]+)",
        "total_trades": r"Total Trades\s+(\d+)",
        "profit_trades": r"Profit Trades[^:]*:\s*(\d+\s*\([\d\.]+%\))",
        "loss_trades": r"Loss Trades[^:]*:\s*(\d+\s*\([\d\.]+%\))",
        "short_trades": r"Short Trades[^:]*:\s*(\d+\s*\([\d\.]+%\))",
        "long_trades": r"Long Trades[^:]*:\s*(\d+\s*\([\d\.]+%\))",
        "balance_dd": r"Balance Drawdown Maximal\s+([\d\s]+\.\d{2}\s*\([\d\.]+%\))",
        "equity_dd": r"Equity Drawdown Maximal\s+([\d\s]+\.\d{2}\s*\([\d\.]+%\))",
        "equity_dd_rel": r"Equity Drawdown Relative\s+([\d\s]+\.\d{2}\s*\([\d\.]+%\))",
        "bars_tested": r"Bars\s+(\d+)",
        "ticks_tested": r"Ticks\s+(\d+)",
        "history_quality": r"History Quality:\s*([\d\.]+%[^\s]*(?:\s*real\s*ticks)?)",
    }
    for key, pat in patterns.items():
        # Report labels carry a trailing colon ("Total Net Profit: -374.14")
        if key not in ("broker_header", "expert", "symbol", "period"):
            pat = pat.replace(r"\s+", r":?\s+").replace(r"\s*\(", r":?\s*\(")
        m = re.search(pat, text)
        if m:
            if key == "period":
                stats["period"] = f"{m.group(1)}-{m.group(2)}"
            elif key == "broker_header":
                stats["broker_header"] = {"broker": m.group(1), "build": m.group(2)}
            else:
                stats[key] = m.group(1).replace("\xa0", " ")
    for k in ("profit_trades", "short_trades", "long_trades"):
        if k in stats:
            m = re.match(r"(\d+)\s*\(([\d\.]+)%\)", stats[k].replace(" ", ""))
            if m:
                stats[k.replace("_trades", "_count")] = int(m.group(1))
                stats[k.replace("_trades", "_win_rate")] = float(m.group(2))
    return stats


def verify_report(report_path, run, expect_from, expect_to):
    """Reject empty or mismatched reports. Returns stats or raises."""
    size = os.path.getsize(report_path)
    mtime = datetime.fromtimestamp(os.path.getmtime(report_path))
    if size < 10000:
        raise FatalError(f"Report suspiciously small ({size} B)")
    if mtime < run["process_start"]:
        raise FatalError(f"Report mtime {mtime} predates process start {run['process_start']}")
    stats = parse_report(report_path)
    expert_reported = stats.get("expert", "").split("\\")[-1]
    if expert_reported not in (EXPERT_NAME, EXPERT_NAME + ".ex5"):
        raise FatalError(f"Report expert mismatch: {stats.get('expert')}")
    if stats.get("symbol") != EXPECTED_SYMBOL:
        raise FatalError(f"Report symbol mismatch: {stats.get('symbol')}")
    if stats.get("period") and (expect_from not in stats["period"] or expect_to not in stats["period"]):
        raise FatalError(f"Report period mismatch: {stats.get('period')} vs {expect_from}-{expect_to}")
    hdr = stats.get("broker_header") or {}
    if hdr.get("broker") != EXPECTED_SERVER:
        raise FatalError(f"Report generated by wrong broker terminal: {hdr}")
    stats["report_size"] = size
    stats["report_mtime"] = mtime.isoformat()
    return stats


def parse_tester_journal(run):
    """Pull the run's own lines from today's tester journal (bars/ticks/model)."""
    log_dir = Path(PU_PRIME_DATA) / "tester" / "logs"
    if not log_dir.exists():
        return {}
    latest = max(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime)
    out = {"journal_file": str(latest)}
    try:
        text = read_text_any(latest)
    except Exception:
        return out
    start = run["process_start"].strftime("%H:%M")
    keys = ("ticks generating", "real ticks", "history begins from",
            "testing of Experts", "final balance", "bars tested", "ticks tested",
            "not started because")
    lines = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ts = parts[2][:5]
        if ts >= start[:5] and any(k in line for k in keys):
            lines.append(line.strip())
    out["journal_excerpt"] = lines[-40:]
    for line in reversed(lines):
        if "final balance" in line:
            out["final_balance_line"] = line
            break
    return out


# ---------------- Tester execution ------------------------------------------

def write_ini(report_name, set_file, from_date, to_date, model=MODEL_REAL_TICKS):
    ini = f"""[Common]
ProxyEnable=0
AutoUpdate=0
[Tester]
Expert={EXPERT_NAME}.ex5
Symbol={EXPECTED_SYMBOL}
Period=M15
FromDate={from_date}
ToDate={to_date}
Deposit=10000
Currency=USD
Leverage=100
Model={model}
Optimization=0
Forward=0
Visual=0
ExecutionDelay=0
Report={report_name}
ReplaceReport=1
ShutdownTerminal=1
"""
    if set_file:
        src = PRESETS / set_file
        if not src.exists():
            raise FatalError(f"Preset not found: {src}")
        TESTER_PROFILES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, TESTER_PROFILES / set_file)
        # Must stay INSIDE the [Tester] section, before [Charts]
        ini += f"ExpertParameters={set_file}\n"
    ini += "[Charts]\n"
    ini_path = Path(PU_PRIME_DATA) / f"{report_name}.ini"
    ini_path.write_text(ini, encoding="utf-8")
    return ini_path


def run_tester(test_id, set_file, from_date, to_date, model=MODEL_REAL_TICKS,
               timeout=1800):
    """Launch tester via /config. PID-scoped supervision only."""
    vantage_before = snapshot_vantage()
    if snapshot_puprime():
        raise FatalError("PU Prime already running; refusing to start a second instance")

    run_id = f"{test_id}_{now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = EVIDENCE / "RUNS" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    report_name = f"DE40_{run_id}"
    ini_path = write_ini(report_name, set_file, from_date, to_date, model=model)
    shutil.copy2(ini_path, run_dir / ini_path.name)

    run = {"test_id": test_id, "run_id": run_id, "set_file": set_file,
           "from": from_date, "to": to_date, "model": model,
           "ini": str(ini_path), "vantage_pids_before": vantage_before,
           "process_start": now()}
    (run_dir / "run_meta.json").write_text(
        json.dumps({k: str(v) for k, v in run.items()}, indent=2))

    log(f"Launching tester. report={report_name} model={model}")
    proc = subprocess.Popen([PU_PRIME_EXE, f"/config:{ini_path}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run["pid"] = proc.pid
    log(f"PID captured: {proc.pid}")

    start = time.time()
    while proc.poll() is None:
        if time.time() - start > timeout:
            stop_pid(proc.pid, "timeout")
            proc.wait(timeout=60)
            raise FatalError(f"Tester timed out after {timeout}s (PID {proc.pid} killed)")
        assert_vantage_alive(vantage_before, "during-test")
        time.sleep(5)
    run["process_end"] = now()
    run["exit_code"] = proc.returncode
    log(f"Process exited code={proc.returncode} after {int(time.time()-start)}s")
    assert_vantage_alive(vantage_before, "after-test")

    # Locate report
    report_path = None
    for ext in (".xml.htm", ".htm", ".html"):
        cand = Path(PU_PRIME_DATA) / f"{report_name}{ext}"
        if cand.exists():
            report_path = cand
            break
    if report_path is None:
        journal = parse_tester_journal(run)
        (run_dir / "failure_journal.json").write_text(json.dumps(journal, indent=2))
        raise FatalError(f"No report produced. Journal excerpt saved to {run_dir}")

    stats = verify_report(report_path, run, from_date, to_date)
    journal = parse_tester_journal(run)
    evidence = {**run, **{"stats": stats, **{k: v for k, v in journal.items()}}}
    evidence = json.loads(json.dumps(evidence, default=str))
    (run_dir / "evidence.json").write_text(json.dumps(evidence, indent=2))
    shutil.copy2(report_path, run_dir / report_path.name)
    shutil.copy2(report_path, EVIDENCE / f"{report_name}.htm")
    log(f"EVIDENCE: {run_dir}")
    return evidence


# ---------------- Genetic optimization -----------------------------------------

def _to_float(s):
    """Lenient string->float for optimization XML cells (None on failure)."""
    if s is None:
        return None
    t = str(s).strip().replace(",", "").replace("\xa0", "")
    if t == "" or t in ("-", "n/a", "N/A", "null", "None"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _to_int(s):
    f = _to_float(s)
    return int(f) if f is not None else None


def _fmt_opt_val(v):
    """Format a Python value for a .set line (MT5 wants true/false, plain numbers)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def parse_set_lines(path):
    """Parse a .set file into (fixed, swept).

    MT5 optimization .set lines:  Name=Value||Start||Step||Stop||Flag
    where Flag 'Y' marks a swept (optimizable) input and anything else ('N')
    marks a fixed value. A plain `Name=Value` line is fixed.

    Returns:
      fixed: {name: value_str}  (non-swept parameters, in file order)
      swept: [{name, value, start, step, stop}]  (swept parameters, in order)
    """
    fixed = {}
    swept = []
    for line in read_text_any(path).splitlines():
        s = line.strip()
        if not s or s.startswith(";") or "=" not in s:
            continue
        name, _, rest = s.partition("=")
        name = name.strip()
        if "||" in rest:
            fields = [f.strip() for f in rest.split("||")]
            if len(fields) >= 5 and fields[4].upper() == "Y":
                swept.append({"name": name, "value": fields[0], "start": fields[1],
                              "step": fields[2], "stop": fields[3]})
            else:
                fixed[name] = fields[0]
        else:
            fixed[name] = rest.strip()
    return fixed, swept


def _naive_grid(swept):
    """Product of per-param step counts across swept inputs (None if malformed)."""
    total = 1
    try:
        for e in swept:
            start, step, stop = float(e["start"]), float(e["step"]), float(e["stop"])
            if step <= 0:
                return None
            n = int(round((stop - start) / step)) + 1
            if n < 1:
                return None
            total *= n
        return total
    except (ValueError, TypeError):
        return None


def load_opt_spec(set_name):
    """Load set/<set_name>.json, a sibling optimization spec.

    Accepted shapes:
      {"InpX": {"start": 0.5, "step": 0.1, "stop": 2.0}, ...}
    or
      {"params": {...}, "fixed": {"InpServerUTC": 3, ...}}

    Returns (params: {name:{start,step,stop}}, fixed: {name:value}) or None.
    """
    spec_path = PRESETS / (set_name + ".json")
    if not spec_path.exists():
        return None
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FatalError(f"Optimization spec must be a JSON object: {spec_path}")
    if isinstance(data.get("params"), dict):
        params = data["params"]
        fixed = data.get("fixed", {})
    else:
        params = {}
        fixed = {}
        for k, v in data.items():
            if k == "fixed" and isinstance(v, dict):
                fixed = v
            else:
                params[k] = v
    if not isinstance(fixed, dict):
        raise FatalError(f"'fixed' must be an object in {spec_path}")
    norm = {}
    for name, rng in params.items():
        if not isinstance(rng, dict) or not all(k in rng for k in ("start", "step", "stop")):
            raise FatalError(f"Spec entry '{name}' needs {{start, step, stop}} in {spec_path}")
        norm[name] = {"start": _fmt_opt_val(rng["start"]),
                      "step": _fmt_opt_val(rng["step"]),
                      "stop": _fmt_opt_val(rng["stop"])}
    return norm, dict(fixed)


def build_opt_set(set_name):
    """Stage the optimization .set into TESTER_PROFILES; return metadata.

    With a JSON spec sibling: fixed params come from the base .set (minus the
    swept names), overlaid by spec 'fixed'; spec params emit 5-field MT5
    optimization lines. Without a spec: the base .set is copied verbatim and
    assumed to already carry 5-field Y-flagged ranges.

    Returns dict {staged_name, fixed, swept, naive_grid, spec_used}.
    """
    src = PRESETS / set_name
    if not src.exists():
        raise FatalError(f"Preset not found: {src}")
    base_fixed, base_swept = parse_set_lines(src)
    TESTER_PROFILES.mkdir(parents=True, exist_ok=True)
    spec = load_opt_spec(set_name)

    if spec is None:
        shutil.copy2(src, TESTER_PROFILES / set_name)
        return {"staged_name": set_name, "fixed": base_fixed, "swept": base_swept,
                "naive_grid": _naive_grid(base_swept), "spec_used": False}

    params, fixed_extra = spec
    spec_names = set(params)
    merged_fixed = {k: v for k, v in base_fixed.items() if k not in spec_names}
    for k, v in fixed_extra.items():
        merged_fixed[k] = v
    merged_fixed = {k: v for k, v in merged_fixed.items() if k not in spec_names}

    lines = [f"; DE40 opt {set_name} - generated {now():%Y-%m-%d %H:%M}"]
    for k in sorted(merged_fixed):
        lines.append(f"{k}={_fmt_opt_val(merged_fixed[k])}")

    swept = []
    for entry in base_swept:
        if entry["name"] in spec_names:
            continue
        swept.append(entry)
        lines.append(f"{entry['name']}={entry['value']}||{entry['start']}||"
                     f"{entry['step']}||{entry['stop']}||Y")

    for name, rng in params.items():
        cur = fixed_extra.get(name)
        if cur is None:
            cur = base_fixed.get(name, rng["start"])
        cur = _fmt_opt_val(cur)
        swept.append({"name": name, "value": cur, "start": rng["start"],
                      "step": rng["step"], "stop": rng["stop"]})
        lines.append(f"{name}={cur}||{rng['start']}||{rng['step']}||{rng['stop']}||Y")

    staged = TESTER_PROFILES / set_name
    staged.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"staged_name": set_name, "fixed": merged_fixed, "swept": swept,
            "naive_grid": _naive_grid(swept), "spec_used": True}


def parse_opt_xml(path):
    """Parse the MT5 optimization results XML (Office SpreadsheetML).

    Column layout of the pass table (terminal-defined): pass, result, profit,
    payoff, profit factor, recovery, sharpe, custom, drawdown, trades, then one
    column per swept input (values only, in .set Y-line order).

    Returns (rows, header). Rows carry parsed stats plus a raw `params` list.
    Returns ([], []) on any parse issue.
    """
    ns = {"x": "urn:schemas-microsoft-com:office:spreadsheet"}
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError:
        return [], []
    row_els = root.findall(".//x:Row", ns)
    if not row_els:
        row_els = root.findall(".//Row")
    if len(row_els) < 2:
        return [], []

    def cells(row):
        cell_els = row.findall("x:Cell", ns)
        if not cell_els:
            cell_els = row.findall("Cell")
        out = []
        for c in cell_els:
            d = c.find("x:Data", ns)
            if d is None:
                d = c.find("Data")
            out.append((d.text or "").strip() if d is not None else "")
        return out

    header = cells(row_els[0])
    rows = []
    for row in row_els[1:]:
        vals = cells(row)
        if len(vals) < 4:
            continue
        profit = _to_float(vals[2])
        pass_i = _to_int(vals[0])
        if profit is None and pass_i is None:
            continue
        rows.append({
            "pass": pass_i,
            "result": _to_float(vals[1]),
            "profit": profit,
            "payoff": _to_float(vals[3]),
            "pf": _to_float(vals[4]) if len(vals) > 4 else None,
            "recovery": _to_float(vals[5]) if len(vals) > 5 else None,
            "sharpe": _to_float(vals[6]) if len(vals) > 6 else None,
            "custom": _to_float(vals[7]) if len(vals) > 7 else None,
            "dd": _to_float(vals[8]) if len(vals) > 8 else None,
            "trades": _to_int(vals[9]) if len(vals) > 9 else None,
            "params": vals[10:] if len(vals) > 10 else [],
        })
    return rows, header


def _coerce_param(s):
    """Best-effort typed value from an optimization XML cell string."""
    if s is None:
        return None
    t = s.strip()
    low = t.lower()
    if low in ("true", "false"):
        return low == "true"
    f = _to_float(t)
    if f is None:
        return t
    return int(f) if f == int(f) else f


def _map_param_values(param_values, swept):
    """Attach swept param names (in .set Y-line order) to XML param columns."""
    out = {}
    names = [e["name"] for e in swept]
    for i, v in enumerate(param_values):
        if i >= len(names):
            break
        out[names[i]] = _coerce_param(v)
    return out


def collect_run_artefacts(report_name):
    """Locate every file the optimizer emitted for this run (data root + tester)."""
    roots = [Path(PU_PRIME_DATA),
             Path(PU_PRIME_DATA) / "tester",
             Path(PU_PRIME_DATA) / "tester" / "cache"]
    found = {}
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for cand in root.glob(f"{report_name}*"):
            if not cand.is_file():
                continue
            key = str(cand)
            if key in seen or cand.suffix.lower() == ".ini":
                continue
            seen.add(key)
            found[cand.name] = cand
    return found


def write_opt_ini(report_name, set_file, from_date, to_date,
                  model=MODEL_REAL_TICKS):
    """Write a [Tester] ini for headless genetic optimization.

    Mirrors write_ini with the optimization deltas:
      * Optimization=2        (fast genetic algorithm; MT5: 0=off, 1=slow
                               complete, 2=fast genetic)
      * Report=<name>.xml      (forces the optimization pass-table XML)
      * OptimizationCriterion omitted -> terminal default; the runner ranks
        passes by net profit itself, so no custom OnTester is required.

    Returns the written ini path (data dir, named <report_name>.ini).
    """
    ini = f"""[Common]
ProxyEnable=0
AutoUpdate=0
[Tester]
Expert={EXPERT_NAME}.ex5
Symbol={EXPECTED_SYMBOL}
Period=M15
FromDate={from_date}
ToDate={to_date}
Deposit=10000
Currency=USD
Leverage=100
Model={model}
Optimization=2
Forward=0
Visual=0
ExecutionDelay=0
Report={report_name}.xml
ReplaceReport=1
ShutdownTerminal=1
ExpertParameters={set_file}
[Charts]
"""
    ini_path = Path(PU_PRIME_DATA) / f"{report_name}.ini"
    ini_path.write_text(ini, encoding="utf-8")
    return ini_path


def _opt_parse_limitation(rows, xml_found, htm_stats):
    notes = []
    if not xml_found:
        notes.append("No optimization XML produced; pass table unavailable.")
    elif not rows:
        notes.append("Optimization XML present but no pass rows could be parsed "
                     "(unrecognized schema / empty table).")
    elif not any(r.get("params") for r in rows):
        notes.append("Parameter values absent from the optimization XML columns.")
    if htm_stats:
        notes.append("Single best-result HTML stats also available (see run artefacts).")
    return "; ".join(notes) if notes else None


def build_opt_summary(test_id, run, rows, swept, xml_found, htm_stats=None):
    ranked = sorted(rows, key=lambda r: (r.get("profit") is not None,
                                         r.get("profit") or float("-inf")),
                    reverse=True)
    top = []
    for i, r in enumerate(ranked[:20]):
        top.append({
            "rank": i + 1,
            "pass": r.get("pass"),
            "net_profit": r.get("profit"),
            "result": r.get("result"),
            "expected_payoff": r.get("payoff"),
            "profit_factor": r.get("pf"),
            "recovery_factor": r.get("recovery"),
            "sharpe": r.get("sharpe"),
            "custom": r.get("custom"),
            "dd_pct": r.get("dd"),
            "total_trades": r.get("trades"),
            "params": _map_param_values(r.get("params", []), swept),
        })
    return {
        "test_id": test_id,
        "run_id": run.get("run_id"),
        "expert": EXPERT_NAME,
        "symbol": EXPECTED_SYMBOL,
        "from": run.get("from"),
        "to": run.get("to"),
        "swept_params": [e["name"] for e in swept],
        "total_passes": len(rows),
        "top_by_net_profit": top,
        "parse_limitation": _opt_parse_limitation(rows, xml_found, htm_stats),
    }


def run_optimizer(test_id, set_file, from_date, to_date, passes=None, timeout=7200):
    """Launch headless genetic optimization via /config. PID-scoped supervision."""
    vantage_before = snapshot_vantage()
    if snapshot_puprime():
        raise FatalError("PU Prime already running; refusing to start a second instance")

    run_id = f"{test_id}_{now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = EVIDENCE / "RUNS" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    set_meta = build_opt_set(set_file)
    report_name = f"DE40_{run_id}"
    ini_path = write_opt_ini(report_name, set_meta["staged_name"], from_date, to_date)
    shutil.copy2(ini_path, run_dir / ini_path.name)

    run = {"test_id": test_id, "run_id": run_id, "set_file": set_file,
           "from": from_date, "to": to_date, "passes": passes,
           "expert": EXPERT_NAME, "ini": str(ini_path),
           "vantage_pids_before": vantage_before,
           "process_start": now(), "swept": set_meta["swept"],
           "naive_grid": set_meta["naive_grid"], "spec_used": set_meta["spec_used"]}
    (run_dir / "run_meta.json").write_text(json.dumps(run, default=str, indent=2))

    log(f"Launching genetic optimizer. report={report_name} passes={passes}")
    proc = subprocess.Popen([PU_PRIME_EXE, f"/config:{ini_path}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run["pid"] = proc.pid
    log(f"PID captured: {proc.pid}")

    start = time.time()
    while proc.poll() is None:
        if time.time() - start > timeout:
            stop_pid(proc.pid, "timeout")
            proc.wait(timeout=60)
            raise FatalError(f"Optimizer timed out after {timeout}s (PID {proc.pid} killed)")
        assert_vantage_alive(vantage_before, "during-optimization")
        time.sleep(5)
    run["process_end"] = now()
    run["exit_code"] = proc.returncode
    log(f"Process exited code={proc.returncode} after {int(time.time()-start)}s")
    assert_vantage_alive(vantage_before, "after-optimization")

    artefacts = collect_run_artefacts(report_name)
    copied = []
    for name, src in artefacts.items():
        shutil.copy2(src, run_dir / name)
        copied.append(name)
    run["artefacts"] = copied

    xml_path = next((artefacts[n] for n in copied if n.lower().endswith(".xml")), None)
    rows, _ = parse_opt_xml(xml_path) if xml_path else ([], [])

    htm_path = next((artefacts[n] for n in copied
                     if n.lower().endswith((".htm", ".html"))), None)
    try:
        htm_stats = parse_report(htm_path) if htm_path else None
    except Exception:
        htm_stats = None

    summary = build_opt_summary(test_id, run, rows, set_meta["swept"],
                                xml_found=(xml_path is not None), htm_stats=htm_stats)
    (run_dir / "opt_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    out_path = EVIDENCE / f"{test_id}_opt_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    log(f"Optimization summary -> {out_path}")

    if proc.returncode != 0 and not rows:
        journal = parse_tester_journal(run)
        (run_dir / "failure_journal.json").write_text(json.dumps(journal, indent=2))

    evidence = json.loads(json.dumps(run, default=str))
    evidence["opt_summary"] = summary
    (run_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
    log(f"EVIDENCE: {run_dir}")
    return evidence


def cmd_opt(args):
    if len(args) < 4:
        raise FatalError("usage: opt <test_id> <set_file> <from> <to> [passes]")
    test_id, set_file, from_date, to_date = args[0], args[1], args[2], args[3]
    try:
        passes = int(args[4]) if len(args) > 4 else None
    except ValueError:
        raise FatalError(f"passes must be an integer, got '{args[4]}'")
    verify_origin_mapping()
    ev = run_optimizer(test_id, set_file, from_date, to_date, passes=passes, timeout=7200)
    print(json.dumps(ev["opt_summary"], indent=2, default=str))


# ---------------- Subcommands ------------------------------------------------

def cmd_identity():
    verify_origin_mapping()
    ev = mt5_identity_check()
    out = EVIDENCE / "RUNS" / f"identity_{now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, indent=2))
    log(f"Identity evidence -> {out}")
    print(json.dumps(ev, indent=2))


def cmd_sync():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=PU_PRIME_EXE):
        raise FatalError(f"mt5.initialize failed: {mt5.last_error()}")
    try:
        acc = None
        for _ in range(30):
            acc = mt5.account_info()
            if acc:
                break
            time.sleep(1)
        if not acc or acc.server != EXPECTED_SERVER:
            raise FatalError("Identity check failed during sync")
        if _PROF["assert_company"] and acc.company != EXPECTED_COMPANY:
            raise FatalError("Company mismatch during sync")
        mt5.symbol_select(EXPECTED_SYMBOL, True)
        bars = mt5.copy_rates_from(EXPECTED_SYMBOL, mt5.TIMEFRAME_M15,
                                   int(datetime(2021, 1, 1).timestamp()), 1_000_000)
        n = 0 if bars is None else len(bars)
        log(f"GER40.s M15 bars now available: {n}")
        if bars is not None and n > 0:
            import datetime as dt
            first = dt.datetime.fromtimestamp(int(bars[0][0]))
            last = dt.datetime.fromtimestamp(int(bars[-1][0]))
            log(f"M15 range: {first} .. {last}")
    finally:
        mt5.shutdown()


def cmd_diag():
    verify_origin_mapping()
    archive_stale_reports()
    ev = run_tester("DIAG_REAL_TICKS", None, "2026.07.01", "2026.07.31",
                    model=MODEL_REAL_TICKS, timeout=1200)
    s = ev["stats"]
    log("DIAGNOSTIC SUMMARY: "
        f"trades={s.get('total_trades')} net={s.get('net_profit')} "
        f"pf={s.get('profit_factor')} bars={s.get('bars_tested')} "
        f"ticks={s.get('ticks_tested')}")


def cmd_test(args):
    if len(args) < 4:
        raise FatalError("usage: test <test_id> <set_file> <from> <to>")
    verify_origin_mapping()
    ev = run_tester(args[0], args[1], args[2], args[3], model=MODEL_REAL_TICKS)
    print(json.dumps(ev["stats"], indent=2))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    try:
        if cmd == "identity":
            cmd_identity()
        elif cmd == "sync":
            cmd_sync()
        elif cmd == "diag":
            cmd_diag()
        elif cmd == "test":
            cmd_test(argv[2:])
        elif cmd == "opt":
            cmd_opt(argv[2:])
        else:
            print(__doc__)
            return 1
    except FatalError as e:
        log(f"HARD FAILURE (fail-closed): {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
