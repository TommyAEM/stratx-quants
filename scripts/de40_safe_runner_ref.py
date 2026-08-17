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
from datetime import datetime
from pathlib import Path

# ---------------- Canonical identity (asserted before every test) ----------
PU_PRIME_EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
PU_PRIME_DATA = r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
VANTAGE_EXE = r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe"

EXPECTED_COMPANY = "PU Prime Ltd"
EXPECTED_SERVER = "PUPrime-Demo"
EXPECTED_ACCOUNT_ENDING = "7739"
EXPECTED_DATA_HASH = "D0E8209F77C8CF37AD8BF550E51FF075"
EXPECTED_SYMBOL = "GER40.s"

EXPERT_NAME = "DE40_X1"
PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "EVIDENCE"
PRESETS = PROJECT / "PRESETS"
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
        raise FatalError(f"Vantage PIDs {missing} disappeared at stage '{stage}'. "
                         f"ABORTING — this runner must never affect Vantage.")
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

        # Hard assertions — fail closed
        if acc.company != EXPECTED_COMPANY:
            raise FatalError(f"Company mismatch: got '{acc.company}'")
        if acc.server != EXPECTED_SERVER:
            raise FatalError(f"Server mismatch: got '{acc.server}'")
        if not str(acc.login).endswith(EXPECTED_ACCOUNT_ENDING):
            raise FatalError(f"Account mismatch: got '*****{str(acc.login)[-4:]}'")
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
        if not acc or acc.company != EXPECTED_COMPANY:
            raise FatalError("Identity check failed during sync")
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
        else:
            print(__doc__)
            return 1
    except FatalError as e:
        log(f"HARD FAILURE (fail-closed): {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
