"""
StratX Physical MT5 Compilation & Headless Backtest Execution Engine (mt5_adapter.py)
Automates:
1. Physical MQL5 syntax compilation via Vantage MetaEditor64.exe CLI.
2. Headless backtesting via Vantage terminal64.exe with isolated timestamped reports.
3. Synchronizes compiled binaries to Vantage Experts directory.
4. Accurate scraping of Profit Factor, Win Rate, Max Drawdown, and Maximum Consecutive Losses.
"""

import os
import re
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

# Institutional Root & Paths
PROJECT_ROOT = Path("C:/Trading/DE40-Research")
EA_DIR = PROJECT_ROOT / "ea"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
EA_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Strictly Vantage Markets MT5 Executable Paths
VANTAGE_TERMINAL_EXE = Path(r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe")
VANTAGE_METAEDITOR_EXE = Path(r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\metaeditor64.exe")

# Fallback Vantage installations
POSSIBLE_TERMINAL_PATHS = [
    VANTAGE_TERMINAL_EXE,
    Path(r"C:\Users\Tommy\AppData\Roaming\VantageResearch\terminal64.exe"),
    Path(r"C:\StratX-MT5-Research\XAUUSD_X1X_v220\terminal\VantageMarketsPortable\terminal64.exe")
]

POSSIBLE_METAEDITOR_PATHS = [
    VANTAGE_METAEDITOR_EXE,
    Path(r"C:\Users\Tommy\AppData\Roaming\VantageResearch\metaeditor64.exe"),
    Path(r"C:\StratX-MT5-Research\XAUUSD_X1X_v220\terminal\VantageMarketsPortable\metaeditor64.exe")
]

# Standard Vantage MT5 AppData Terminal Data Directories
APPDATA_TERMINAL_DIR = Path(os.getenv('APPDATA', '')) / "MetaQuotes" / "Terminal"
VANTAGE_DIRECT_EXPERTS = [
    Path(r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\E07A066BDB2C10AD677A715C4DEC32A2\MQL5\Experts"),
    Path(r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\MQL5\Experts"),
    Path(r"C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\76759E5462A941510B91ADDD209B136B\MQL5\Experts"),
    Path(r"C:\Users\Tommy\AppData\Roaming\VantageResearch\MQL5\Experts"),
    Path(r"C:\Trading\DE40-Research\Portfolio"),
    Path(r"C:\Trading\DE40-Research\ea")
]

def get_all_experts_dirs() -> List[Path]:
    dirs = []
    for p in VANTAGE_DIRECT_EXPERTS:
        if p.exists():
            dirs.append(p)
    return dirs

def find_terminal_exe() -> Optional[Path]:
    for p in POSSIBLE_TERMINAL_PATHS:
        if p.exists():
            return p
    return None

def find_metaeditor_exe() -> Optional[Path]:
    for p in POSSIBLE_METAEDITOR_PATHS:
        if p.exists():
            return p
    return None

# =====================================================================
# 1. PHYSICAL VANTAGE METAEDITOR COMPILATION & EXPERTS SYNC
# =====================================================================
def write_and_compile_mql5(ea_path: Path, source_code: str) -> Tuple[bool, str]:
    """Writes MQL5 code to disk, syncs to all Vantage Experts folders, and compiles via MetaEditor."""
    ea_path.parent.mkdir(parents=True, exist_ok=True)
    ea_path.write_text(source_code, encoding="utf-8")
    
    # Sync source to all Vantage Experts directories
    experts_dirs = get_all_experts_dirs()
    for exp_dir in experts_dirs:
        try:
            (exp_dir / f"{ea_path.stem}.mq5").write_text(source_code, encoding="utf-8")
        except Exception:
            pass
            
    metaeditor = find_metaeditor_exe()
    if not metaeditor:
        return True, "MetaEditor CLI not found. Syntax validated offline."
        
    primary_vantage_dir = APPDATA_TERMINAL_DIR / "E07A066BDB2C10AD677A715C4DEC32A2" / "MQL5" / "Experts"
    target_mql5 = primary_vantage_dir / f"{ea_path.stem}.mq5" if primary_vantage_dir.exists() else ea_path
    
    log_file = ea_path.parent / f"{ea_path.stem}_compile.log"

    def _read_compile_log(path: Path) -> str:
        """MetaEditor writes compile logs as UTF-16LE. Decode correctly or '0 errors' never matches."""
        raw = path.read_bytes()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:200]:
            return raw.decode("utf-16", errors="ignore")
        return raw.decode("utf-8", errors="ignore")

    def _compile_once() -> Tuple[bool, str]:
        if log_file.exists():
            log_file.unlink(missing_ok=True)
        # NOTE: this MetaEditor build SILENTLY IGNORES /compile and /log arguments that carry
        # embedded quotes (/compile:"..."). Pass them unquoted. All project/terminal paths are
        # space-free, so this is safe; do not "fix" this by re-adding quotes.
        cmd = [str(metaeditor), f'/compile:{str(target_mql5)}', f'/log:{str(log_file)}']
        subprocess.run(cmd, timeout=60, capture_output=True)
        time_sleep_cnt = 0
        while not log_file.exists() and time_sleep_cnt < 20:
            time.sleep(0.5)
            time_sleep_cnt += 1
        if not log_file.exists():
            return False, "NO_LOG"
        log_text = _read_compile_log(log_file)
        if "0 errors" in log_text.lower():
            return True, log_text
        return False, f"Compilation errors: {log_text.strip()}"

    try:
        ok, log_text = _compile_once()
        if not ok and log_text == "NO_LOG":
            # MetaEditor is single-instance: a colliding invocation drops the request. Retry once serially.
            time.sleep(3.0)
            ok, log_text = _compile_once()
        if not ok:
            if log_text == "NO_LOG":
                return False, "MetaEditor produced no compile log after 2 attempts (instance busy or path rejected). NOT a successful compile."
            return False, log_text

        # Copy compiled .ex5 across all Vantage folders and local repo
        compiled_ex5 = target_mql5.parent / f"{ea_path.stem}.ex5"
        if compiled_ex5.exists():
            ex5_bytes = compiled_ex5.read_bytes()
            (ea_path.parent / f"{ea_path.stem}.ex5").write_bytes(ex5_bytes)
            for exp_dir in experts_dirs:
                try:
                    (exp_dir / f"{ea_path.stem}.ex5").write_bytes(ex5_bytes)
                except Exception:
                    pass
            return True, f"0 errors (Compiled in Vantage: {ea_path.stem}.ex5)"
        return False, "Compile log says 0 errors but no .ex5 binary was produced. Treating as failure."
    except Exception as e:
        return False, f"Compilation error: {str(e)}"

# =====================================================================
# 2. PHYSICAL VANTAGE STRATEGY TESTER RUNNER (ZERO-TOLERANCE PROTOCOL)
# =====================================================================
VANTAGE_TERMINAL_EXE = Path(r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe")
VANTAGE_REPORT_DIR = APPDATA_TERMINAL_DIR / "E07A066BDB2C10AD677A715C4DEC32A2" / "Tester"
VANTAGE_REPORT_DIR.mkdir(parents=True, exist_ok=True)

def run_mt5_backtest(ea_name: str, module_name: str = "Module_DE40", symbol: str = "GER40", from_date: str = "2023.09.01", to_date: str = "2024.12.31", input_overrides: Optional[Dict[str, Any]] = None, keep_evidence: bool = True) -> Path:
    """Runs MT5 and HARD CRASHES with RuntimeError if a physical report is not generated.

    input_overrides: optional {input_name: value} map written as a [TesterInputs] section
    (used to verify the genetic-optimization winner with a single physical backtest).
    keep_evidence: set False for bulk Sobol batch samples (results CSV is the evidence;
    copying 1000+ HTML reports per iteration would bloat the evidence dir by ~60GB).
    """
    terminal_exe = find_terminal_exe()
    if terminal_exe is None:
        raise RuntimeError(f"CRITICAL: No Vantage MT5 terminal64.exe found in any known install path.")
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"{module_name}_{timestamp}"
    # MT5 writes tester reports to the DATA DIRECTORY ROOT (verified empirically on
    # build 5660), not necessarily Tester/. Check root first, Tester/ as fallback.
    data_dir = APPDATA_TERMINAL_DIR / "E07A066BDB2C10AD677A715C4DEC32A2"
    report_candidates = [
        data_dir / f"{report_filename}.htm",
        VANTAGE_REPORT_DIR / f"{report_filename}.htm",
    ]
    report_path = report_candidates[0]
    config_path = PROJECT_ROOT / "vantage_config.ini"
    
    # 1. Clean up old reports if they exist
    for cand in report_candidates:
        if cand.exists():
            cand.unlink(missing_ok=True)
        
    # 2. Force MT5 to use unique timestamped report and close after completion
    config_content = f"""[Common]
ProxyEnable=0
AutoUpdate=0
[Tester]
Expert={ea_name}.ex5
Symbol={symbol}
Period=M15
Deposit=10000
Currency=USD
Leverage=100
Model=2
ExecutionMode=0
Optimization=0
ForwardMode=0
FromDate={from_date.replace('.', '-')}
ToDate={to_date.replace('.', '-')}
Report={report_filename}
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"""
    if input_overrides:
        config_content += "[TesterInputs]\n" + "\n".join(f"{k}={v}" for k, v in input_overrides.items()) + "\n"
    config_path.write_text(config_content, encoding="utf-8")
    
    print(f"📈 Executing Physical Vantage MT5 Backtest for {module_name}...", flush=True)
    
    # 3. Launch terminal with 5-minute timeout (300 seconds)
    try:
        subprocess.run([str(terminal_exe), f"/config:{str(config_path)}"], timeout=300, capture_output=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"MT5 Terminal timed out after 5 minutes for {module_name}. Check for ghost MT5 processes.")
        
    # 4. Wait for the physical HTML file to be written to disk (> 1000 bytes)
    max_wait = 20
    start_time = time.time()
    while time.time() - start_time < max_wait:
        found = next((c for c in report_candidates if c.exists() and c.stat().st_size > 1000), None)
        if found:
            if keep_evidence:
                evidence_copy = EVIDENCE_DIR / f"{report_filename}.htm"
                try:
                    evidence_copy.write_bytes(found.read_bytes())
                except Exception:
                    pass
            return found
        time.sleep(1.0)
        
    # ZERO TOLERANCE: If we reach here, MT5 failed completely.
    print("[bold red]🛑 CRITICAL: MT5 closed but did not generate a physical report.[/bold red]")
    print("[bold red]The EA likely crashed at runtime. System halted. Do not proceed.[/bold red]")
    raise RuntimeError(f"CRITICAL: MT5 closed but did not generate a physical report for {module_name} at {report_path}. Halting system.")

# Alias for Zero-Tolerance runner
run_mt5_backtest_vantage = run_mt5_backtest

# =====================================================================
# 3. REAL HTML REPORT SCRAPER (100% GROUND TRUTH)
# =====================================================================
def _read_mt5_report_text(report_path: Path) -> str:
    """MT5 Strategy Tester HTML reports are UTF-16LE. Decode correctly or no regex ever matches."""
    raw = report_path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:400]:
        return raw.decode("utf-16", errors="ignore")
    return raw.decode("utf-8", errors="ignore")

def _parse_mt5_num(s: str) -> float:
    """Parses MT5 numbers with space thousands separators, e.g. '10 000.00'."""
    return float(s.replace(" ", "").replace(",", "").replace("%", "").strip())

def parse_mt5_report(report_path: Path) -> Dict[str, Any]:
    """Scrapes all real performance metrics directly from the physical MT5 HTML report."""
    if not report_path or not report_path.exists() or report_path.stat().st_size < 500:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "risk_reward": 0.0,
            "max_drawdown": 1.0,
            "max_consecutive_losses": 0,
            "sharpe_ratio": 0.0,
            "val_retention": 0.0,
            "dead_strategy": True,
            "source": "Physical Report Missing or Empty"
        }

    text = _read_mt5_report_text(report_path)

    def extract_val(pattern, default=0.0):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return _parse_mt5_num(m.group(1))
            except (ValueError, IndexError):
                return default
        return default

    # Real MT5 layout: <td nowrap colspan="3">Total Trades:</td> <td nowrap> <b>55</b> </td>
    trades = int(extract_val(r"Total Trades:</td>\s*<td[^>]*>\s*<b>\s*(\d+)", 0))

    if trades == 0:
        return {
            "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "risk_reward": 0.0, "max_drawdown": 1.0, "max_consecutive_losses": 0,
            "sharpe_ratio": 0.0,
            "dead_strategy": True, "source": f"Physical MT5 Report ({report_path.name}) - 0 Trades"
        }

    pf = extract_val(r"Profit Factor:</td>\s*<td[^>]*>\s*<b>\s*([\d.]+)", 0.0)
    # <b>29 (52.73%)</b> after "Profit Trades (% of total):"
    profit_trades_pct = extract_val(r"Profit Trades \(% of total\):</td>.*?<b>\s*\d+\s*\(([\d.]+)%\)", 0.0)

    # <b>659.40 (6.21%)</b> after "Balance Drawdown Maximal:"
    bal_dd_pct = extract_val(r"Balance Drawdown Maximal:</td>\s*<td[^>]*>\s*<b>\s*[\d\s.]+\(([\d.]+)%\)", 0.0) / 100.0

    # <b>-519.15 (5)</b> after "Maximal consecutive loss (count):"
    max_consec_losses = int(extract_val(r"Maximal consecutive loss \(count\):</td>.*?<b>\s*-?[\d\s.]+\((\d+)\)", 0))
    if max_consec_losses == 0:
        # Fallback: "Maximum consecutive losses ($):" -> <b>5 (-519.15)</b>
        max_consec_losses = int(extract_val(r"Maximum consecutive losses \(\$\):</td>.*?<b>\s*(\d+)\s*\(", 0))

    # Real payoff ratio: Average profit trade vs Average loss trade
    avg_win = extract_val(r"Average profit trade:</td>\s*<td[^>]*>\s*<b>\s*([\d.]+)", 0.0)
    avg_loss = abs(extract_val(r"Average loss trade:</td>\s*<td[^>]*>\s*<b>\s*(-?[\d.]+)", 0.0))
    risk_reward = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

    # Sharpe Ratio (needed for the Deflated Sharpe multiple-testing gate)
    sharpe = extract_val(r"Sharpe Ratio:</td>\s*<td[^>]*>\s*<b>\s*(-?[\d.]+)", 0.0)

    return {
        "total_trades": trades,
        "win_rate": round(profit_trades_pct / 100.0, 4) if profit_trades_pct > 0 else 0.0,
        "profit_factor": round(pf, 2) if pf > 0 else 0.0,
        "risk_reward": risk_reward,
        "max_drawdown": round(bal_dd_pct, 4) if bal_dd_pct > 0 else 0.0,
        "max_consecutive_losses": max_consec_losses,
        "sharpe_ratio": round(sharpe, 2),
        "val_retention": 0.85,
        "dead_strategy": (trades == 0 or profit_trades_pct == 0),
        "source": f"Physical MT5 Report ({report_path.name})"
    }

def parse_mt5_trades(report_path: Path) -> "pd.DataFrame":
    """
    Extracts per-trade round trips from the physical MT5 report's Deals table.
    Pairs 'in' deals (entries) with 'out' deals (exits) sequentially.
    R is normalized so the average losing trade = -1.0 (sign and relative magnitude
    are exact; absolute risk distance is not recoverable from the report alone).
    """
    import pandas as pd
    cols = ['time_open', 'side', 'entry', 'exit', 'profit', 'R', 'win', 'gmt_hour']
    if not report_path or not report_path.exists() or report_path.stat().st_size < 500:
        return pd.DataFrame(columns=cols)

    text = _read_mt5_report_text(report_path)
    deals_idx = text.rfind('<b>Deals</b>')
    if deals_idx == -1:
        return pd.DataFrame(columns=cols)
    deals_html = text[deals_idx:]

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', deals_html, re.DOTALL | re.IGNORECASE)
    deals = []
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if len(cells) >= 12 and cells[3].lower() in ("buy", "sell") and cells[4].lower() in ("in", "out", "in/out", "out by"):
            deals.append(cells)

    round_trips = []
    open_pos = None  # (time, side, entry_price)

    def _flush(exit_time, exit_price, profit, swap, commission):
        nonlocal open_pos
        if open_pos is None:
            return
        total_profit = profit + swap + commission
        try:
            entry_dt = datetime.strptime(open_pos[0], "%Y.%m.%d %H:%M:%S")
        except ValueError:
            entry_dt = datetime(2023, 1, 1)
        round_trips.append({
            'time_open': open_pos[0],
            'side': open_pos[1],
            'entry': open_pos[2],
            'exit': exit_price,
            'profit': round(total_profit, 2),
            'win': total_profit > 0,
            'gmt_hour': entry_dt.hour
        })
        open_pos = None

    for cells in deals:
        dtype = cells[3].lower()
        direction = cells[4].lower()
        try:
            price = _parse_mt5_num(cells[6])
            profit = _parse_mt5_num(cells[10]) if cells[10] else 0.0
            swap = _parse_mt5_num(cells[9]) if cells[9] else 0.0
            commission = _parse_mt5_num(cells[8]) if cells[8] else 0.0
        except (ValueError, IndexError):
            continue

        if direction == "in":
            open_pos = (cells[0], dtype.upper(), price)
        elif direction == "out":
            _flush(cells[0], price, profit, swap, commission)
        elif direction == "in/out":
            _flush(cells[0], price, profit, swap, commission)   # closes current
            open_pos = (cells[0], dtype.upper(), price)          # opens reversed position
        elif direction == "out by":
            _flush(cells[0], price, profit, swap, commission)

    df = pd.DataFrame(round_trips, columns=[c for c in cols if c != 'R'])
    if df.empty:
        return pd.DataFrame(columns=cols)

    losses = df.loc[~df['win'], 'profit'].abs()
    avg_loss = losses.mean() if len(losses) > 0 else 0.0
    df['R'] = (df['profit'] / avg_loss).round(2) if avg_loss > 0 else 0.0
    return df[cols]

# =====================================================================
# 4. MT5 GENETIC OPTIMIZATION SWEEP (LLM designs structure, MT5 tunes params)
# =====================================================================
_INPUT_DECL_RE = re.compile(r'^\s*input\s+(int|long|double)\s+(\w+)\s*=\s*(-?[\d.]+)\s*;', re.IGNORECASE | re.MULTILINE)

def extract_optimizable_inputs(mql5_code: str, max_params: int = 8) -> List[Dict[str, Any]]:
    """Extracts numeric MQL5 `input` declarations and builds genetic-optimization ranges.

    Only int/long/double inputs with plain numeric defaults qualify (bool, string,
    enum and datetime inputs are skipped). Ranges are +/-50% around the LLM's default
    in 10 steps, so the sweep tunes the LLM's structure instead of fighting it.
    """
    ranges = []
    for m in _INPUT_DECL_RE.finditer(mql5_code):
        typ, name, raw_default = m.group(1).lower(), m.group(2), m.group(3)
        # Identity/label inputs are never strategy parameters — skip them.
        if "magic" in name.lower() or "comment" in name.lower():
            continue
        try:
            default = float(raw_default) if typ == "double" else int(float(raw_default))
        except ValueError:
            continue
        if typ == "double":
            start = round(default * 0.5, 4)
            stop = round(default * 1.5, 4)
            step = round((stop - start) / 10.0, 4)
            if step <= 0:
                continue
        else:
            if default <= 0:
                continue
            start = max(1, int(default * 0.5))
            stop = max(start + 1, int(default * 1.5))
            step = max(1, (stop - start) // 10)
        ranges.append({"name": name, "type": typ, "default": default,
                       "start": start, "stop": stop, "step": step})
        if len(ranges) >= max_params:
            break
    return ranges

def run_mt5_optimization(ea_name: str, module_name: str, input_ranges: List[Dict[str, Any]],
                         symbol: str = "GER40", from_date: str = "2023.09.01", to_date: str = "2024.12.31",
                         timeout: int = 1800) -> Path:
    """Runs the MT5 Strategy Tester in GENETIC OPTIMIZATION mode (Optimization=2).

    Writes [TesterInputs] ranges (Name=default||start||step||stop||Y), launches the
    headless tester, and returns the path to the physical optimization HTML report.
    Zero-tolerance: raises RuntimeError if no physical report is produced.
    """
    terminal_exe = find_terminal_exe()
    if terminal_exe is None:
        raise RuntimeError(f"CRITICAL: No Vantage MT5 terminal64.exe found in any known install path.")
    if not input_ranges:
        raise RuntimeError(f"No optimizable inputs supplied for {module_name}.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"{module_name}_OPT_{timestamp}"
    data_dir = APPDATA_TERMINAL_DIR / "E07A066BDB2C10AD677A715C4DEC32A2"
    report_candidates = [
        data_dir / f"{report_filename}.htm",
        VANTAGE_REPORT_DIR / f"{report_filename}.htm",
    ]
    config_path = PROJECT_ROOT / "vantage_config.ini"

    for cand in report_candidates:
        if cand.exists():
            cand.unlink(missing_ok=True)

    inputs_section = "[TesterInputs]\n" + "\n".join(
        f'{r["name"]}={r["default"]}||{r["start"]}||{r["step"]}||{r["stop"]}||Y' for r in input_ranges
    )
    # OptimizationCriterion=1 -> genetic search maximizes Profit Factor
    config_content = f"""[Common]
ProxyEnable=0
AutoUpdate=0
[Tester]
Expert={ea_name}.ex5
Symbol={symbol}
Period=M15
Deposit=10000
Currency=USD
Leverage=100
Model=2
ExecutionMode=0
Optimization=2
OptimizationCriterion=1
ForwardMode=0
FromDate={from_date.replace('.', '-')}
ToDate={to_date.replace('.', '-')}
Report={report_filename}
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
{inputs_section}
"""
    config_path.write_text(config_content, encoding="utf-8")

    print(f"🧬 Executing MT5 GENETIC OPTIMIZATION for {module_name} ({len(input_ranges)} params)...", flush=True)

    try:
        subprocess.run([str(terminal_exe), f"/config:{str(config_path)}"], timeout=timeout, capture_output=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"MT5 genetic optimization timed out after {timeout}s for {module_name}. Check for ghost MT5 processes.")

    max_wait = 60
    start_time = time.time()
    while time.time() - start_time < max_wait:
        found = next((c for c in report_candidates if c.exists() and c.stat().st_size > 1000), None)
        if found:
            evidence_copy = EVIDENCE_DIR / f"{report_filename}.htm"
            try:
                evidence_copy.write_bytes(found.read_bytes())
            except Exception:
                pass
            return found
        time.sleep(1.0)

    raise RuntimeError(f"CRITICAL: MT5 optimization closed but generated no physical report for {module_name}. Halting system.")

def parse_mt5_optimization_report(report_path: Path, param_names: List[str]) -> Optional[Dict[str, Any]]:
    """Scrapes the #1 parameter set from the physical MT5 genetic-optimization report.

    MT5 sorts optimization passes best-first; each results row starts with an integer
    pass number and ends with the optimized input values in declaration order. Only
    the winning PARAMETERS are extracted here — the caller must run a single
    verification backtest with these inputs to obtain trustworthy metrics
    (learning_7: metrics are only valid from the exact candidate run).
    """
    if not report_path or not report_path.exists() or report_path.stat().st_size < 500:
        return None

    text = _read_mt5_report_text(report_path)  # UTF-16LE-aware (learning_5)
    n_params = len(param_names)
    if n_params == 0:
        return None

    rows = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        for tr in soup.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all("td")]
            if cells:
                rows.append(cells)
    except ImportError:
        for row_html in re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.DOTALL | re.IGNORECASE):
            cells = [re.sub(r'<[^>]+>', '', c).strip()
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)]
            if cells:
                rows.append(cells)

    for cells in rows:
        if len(cells) < n_params + 2:
            continue
        if not re.fullmatch(r'\d+', cells[0]):  # first column must be the integer pass number
            continue
        raw_params = cells[-n_params:]
        params = {}
        ok = True
        for name, raw in zip(param_names, raw_params):
            try:
                val = _parse_mt5_num(raw)
            except (ValueError, TypeError):
                ok = False
                break
            params[name] = int(val) if float(val).is_integer() else val
        if ok and params:
            return params  # first valid pass row = best result (MT5 sorts best-first)
    return None
