#!/usr/bin/env python3
"""Sequential MT5 tester batch over a dir of .set files.

Usage: run_set_batch.py <expert> <set_dir> <prefix> <from> <to> [tag]

Runs de40_runner.py test for every <set_dir>/<prefix>_*.set, copying the
expert's trade CSV (magic from the set's InpMagic or default per expert map)
to evidence/<tag>_<config_id>_trades.csv. Writes evidence/<tag>_batch_summary.json
with per-config stats parsed from the runner output.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PY = sys.executable
PROJECT = Path(__file__).resolve().parent.parent
RUNNER = PROJECT / "scripts" / "de40_runner.py"
COMMON = Path(r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\common\Files")

DEFAULT_MAGIC = {
    "DE40_BRKRT_HARNESS": 4100,
    "DE40_EXHREJ_HARNESS": 4200,
    "DE40_OBREC_HARNESS": 4300,
    "DE40_VPPOC_HARNESS": 4400,
    "DE40_SOT_HOST_v0.1": 4000,
}


def wait_terminal_free(timeout=120):
    import time
    q = ("Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
         "Select-Object -ExpandProperty ProcessId")
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", q],
                             capture_output=True, text=True).stdout.strip()
        pids = [p for p in out.split() if p.isdigit()]
        # ignore the live Vantage terminals (different exe); CIM filter is by name only,
        # so check each pid's exe path
        busy = False
        for p in pids:
            ex = subprocess.run(["powershell", "-NoProfile", "-Command",
                                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={p}\").ExecutablePath"],
                                capture_output=True, text=True).stdout.strip()
            if "MetaTrader 5" in ex or "VantageResearch" in ex:
                busy = True
        if not busy:
            return True
        time.sleep(5)
    return False

def parse_stats(out):
    m = re.search(r'\{\s*"_raw_header".*\}\s*$', out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def main(argv):
    expert, set_dir, prefix, frm, to = argv[1], Path(argv[2]), argv[3], argv[4], argv[5]
    tag = argv[6] if len(argv) > 6 else prefix
    sets = sorted(set_dir.glob(f"{prefix}_*.set"))
    summary = {}
    for s in sets:
        cid = s.stem
        magic = DEFAULT_MAGIC.get(expert, 4000)
        for line in s.read_text(encoding="utf-8").splitlines():
            if line.startswith("InpMagic="):
                magic = int(line.split("=")[1])
        wait_terminal_free()
        staged = PROJECT / "set" / s.name
        if not staged.exists() or staged.read_bytes() != s.read_bytes():
            shutil.copy2(s, staged)
        env = dict(os.environ, DE40_EXPERT=expert)
        r = subprocess.run([PY, str(RUNNER), "test", f"{tag}_{cid}", s.name, frm, to],
                           capture_output=True, text=True, env=env, cwd=str(PROJECT))
        stats = parse_stats(r.stdout)
        wait_terminal_free()
        src = COMMON / f"DE40X1_TRADES_{magic}.csv"
        dst = PROJECT / "evidence" / f"{tag}_{cid}_trades.csv"
        if src.exists():
            shutil.copy2(src, dst)
        summary[cid] = {
            "set": s.name,
            "trades": (stats or {}).get("total_trades"),
            "wr": (stats or {}).get("profit_win_rate"),
            "pf": (stats or {}).get("profit_factor"),
            "net": (stats or {}).get("net_profit"),
            "dd_pct": (stats or {}).get("equity_dd"),
            "exit_ok": r.returncode == 0 and stats is not None,
        }
        print(cid, json.dumps(summary[cid]), flush=True)
    (PROJECT / "evidence" / f"{tag}_batch_summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8")
    print("BATCH_SUMMARY_WRITTEN")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
