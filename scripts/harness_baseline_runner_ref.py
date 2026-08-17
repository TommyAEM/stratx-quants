#!/usr/bin/env python3
"""
DE40 Harness Baseline Runner
=============================
Runs baseline FIT/VAL/OOS tests for the 4 Phase-2 harness EAs:
  - DE40_BR_Harness   (Break & Retest)
  - DE40_FABLE_Harness (FABLE-2 Exhaustion)
  - DE40_FVG_Harness   (Fair Value Gap)
  - DE40_LIQ_Harness   (Liquidity Sweep)

Reuses de40_safe_runner identity assertions and PID-scoped safety.

Usage:
  python harness_baseline_runner.py fit          # all 4 FIT baselines
  python harness_baseline_runner.py fit <ea>     # single EA FIT baseline
  python harness_baseline_runner.py val <ea>     # single EA VAL
  python harness_baseline_runner.py oos <ea>     # single EA OOS
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import de40_safe_runner as sr

PROJECT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT / "EVIDENCE"
PRESETS = PROJECT / "PRESETS"

HARNESSES = {
    "BR":    {"expert": "DE40_BR_Harness",    "magic": 440300001},
    "FABLE": {"expert": "DE40_FABLE_Harness",  "magic": 440200001},
    "FVG":   {"expert": "DE40_FVG_Harness",    "magic": 440400001},
    "LIQ":   {"expert": "DE40_LIQ_Harness",    "magic": 440100001},
}

PERIODS = {
    "fit": ("2023.01.01", "2024.12.31"),
    "val": ("2025.01.01", "2025.12.31"),
    "oos": ("2026.01.01", "2026.07.31"),
}

def write_harness_ini(expert_name, report_name, from_date, to_date,
                      set_file=None, model=4):
    """Generate tester INI for a harness EA."""
    ini = f"""[Common]
ProxyEnable=0
AutoUpdate=0
[Tester]
Expert={expert_name}.ex5
Symbol={sr.EXPECTED_SYMBOL}
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
            raise sr.FatalError(f"Preset not found: {src}")
        sr.TESTER_PROFILES.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src, sr.TESTER_PROFILES / set_file)
        ini += f"ExpertParameters={set_file}\n"
    ini += "[Charts]\n"
    ini_path = Path(sr.PU_PRIME_DATA) / f"{report_name}.ini"
    ini_path.write_text(ini, encoding="utf-8")
    return ini_path


def run_harness_test(harness_key, period_key, set_file=None, timeout=1800):
    """Run a single harness baseline test."""
    h = HARNESSES[harness_key]
    from_date, to_date = PERIODS[period_key]

    sr.verify_origin_mapping()
    sr.archive_stale_reports()

    run_id = f"{harness_key}_{period_key.upper()}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir = EVIDENCE / "RUNS" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    report_name = f"DE40_{run_id}"
    ini_path = write_harness_ini(h["expert"], report_name, from_date, to_date,
                                 set_file=set_file)
    import shutil
    shutil.copy2(ini_path, run_dir / ini_path.name)

    run = {
        "test_id": f"{harness_key}_{period_key.upper()}",
        "run_id": run_id,
        "harness": harness_key,
        "expert": h["expert"],
        "magic": h["magic"],
        "period": period_key,
        "set_file": set_file,
        "from": from_date,
        "to": to_date,
        "model": 4,
        "ini": str(ini_path),
        "process_start": sr.now(),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps({k: str(v) for k, v in run.items()}, indent=2))

    sr.log(f"Launching {h['expert']} {period_key.upper()} "
           f"({from_date} to {to_date})")

    import subprocess
    proc = subprocess.Popen(
        [sr.PU_PRIME_EXE, f"/config:{ini_path}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run["pid"] = proc.pid
    sr.log(f"PID captured: {proc.pid}")

    start = time.time()
    vantage_before = sr.snapshot_vantage()
    while proc.poll() is None:
        if time.time() - start > timeout:
            sr.stop_pid(proc.pid, "timeout")
            proc.wait(timeout=60)
            raise sr.FatalError(f"Timed out after {timeout}s")
        sr.assert_vantage_alive(vantage_before, f"during-{run_id}")
        time.sleep(5)

    run["process_end"] = sr.now()
    run["exit_code"] = proc.returncode
    sr.log(f"Process exited code={proc.returncode} "
           f"after {int(time.time()-start)}s")
    sr.assert_vantage_alive(vantage_before, f"after-{run_id}")

    report_path = None
    for ext in (".xml.htm", ".htm", ".html"):
        cand = Path(sr.PU_PRIME_DATA) / f"{report_name}{ext}"
        if cand.exists():
            report_path = cand
            break

    if report_path is None:
        journal = sr.parse_tester_journal(run)
        (run_dir / "failure_journal.json").write_text(
            json.dumps(journal, indent=2))
        raise sr.FatalError(f"No report produced for {run_id}")

    stats = sr.parse_report(report_path)
    journal = sr.parse_tester_journal(run)
    evidence = {**run, "stats": stats,
                **{k: v for k, v in journal.items() if k != "journal_file"}}
    evidence = json.loads(json.dumps(evidence, default=str))
    (run_dir / "evidence.json").write_text(json.dumps(evidence, indent=2))
    shutil.copy2(report_path, run_dir / report_path.name)
    shutil.copy2(report_path, EVIDENCE / f"{report_name}.htm")

    sr.log(f"EVIDENCE: {run_dir}")
    s = stats
    sr.log(f"RESULT: trades={s.get('total_trades')} "
           f"net={s.get('net_profit')} "
           f"pf={s.get('profit_factor')} "
           f"wr={s.get('profit_trades','?')}")
    return evidence


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    period = sys.argv[1].lower()
    if period not in PERIODS:
        print(f"Unknown period: {period}. Use: fit, val, oos")
        return 1

    targets = sys.argv[2:] if len(sys.argv) > 2 else list(HARNESSES.keys())
    for key in targets:
        key = key.upper()
        if key not in HARNESSES:
            print(f"Unknown harness: {key}. Use: BR, FABLE, FVG, LIQ")
            continue
        try:
            ev = run_harness_test(key, period)
            print(json.dumps(ev.get("stats", {}), indent=2))
        except sr.FatalError as e:
            sr.log(f"FAILED {key} {period.upper()}: {e}")
            continue
    return 0


if __name__ == "__main__":
    sys.exit(main())
