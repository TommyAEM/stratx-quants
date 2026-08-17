"""
=============================================================================
REAL VANTAGE MT5 QUANTITATIVE BACKTEST ENGINE
Direct connection to Vantage Markets MT5 Terminal via official MetaTrader5 API.
Scrapes and simulates strategies against 100% real historical broker bars.
=============================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

PROJECT_ROOT = Path("C:/Trading/DE40-Research")
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

VANTAGE_TERMINAL_EXE = r"C:\Users\Tommy\AppData\Roaming\Vantage Markets MT5 Terminal\terminal64.exe"
DATA_FILE = DATA_DIR / "vantage_ger40_m15_real.csv"

def sync_vantage_real_data(symbol: str = "GER40", start_date: datetime = datetime(2023, 9, 1), end_date: datetime = datetime(2024, 12, 31)) -> pd.DataFrame:
    """Downloads real historical M15 data directly from Vantage MT5."""
    if DATA_FILE.exists() and DATA_FILE.stat().st_size > 50000:
        df = pd.read_csv(DATA_FILE)
        df['time'] = pd.to_datetime(df['time'])
        return df
        
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 python package not installed.")
        
    init_res = mt5.initialize(path=VANTAGE_TERMINAL_EXE)
    if not init_res:
        raise RuntimeError(f"Failed to connect to Vantage MT5 at {VANTAGE_TERMINAL_EXE}. Error: {mt5.last_error()}")
        
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_date, end_date)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Could not retrieve historical bars for {symbol} from Vantage MT5.")
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.to_csv(DATA_FILE, index=False)
    return df

def run_real_vantage_backtest(module_name: str, mql5_code: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], pd.DataFrame, Path]:
    """
    Executes a REAL physical backtest of the actual MQL5 code in the Vantage MT5
    Strategy Tester (terminal64.exe headless) and scrapes the physical HTML report.

    INTEGRITY NOTE: the previous version of this function accepted mql5_code but
    silently DISCARDED it, running one of 5 hardcoded Python bar-replay simulations
    selected by module-name substring. The Architect's mutations therefore had zero
    effect on measured metrics, and every module name fell through to the same
    default SMC sweep simulation (producing identical metrics and false
    "alpha duplication" rejections). Fixed: the compiled EA is now what gets tested.
    """
    from orchestrator.mt5_adapter import (
        write_and_compile_mql5,
        run_mt5_backtest,
        parse_mt5_report,
        parse_mt5_trades,
        find_terminal_exe,
    )

    if find_terminal_exe() is None:
        raise RuntimeError(f"CRITICAL: Vantage MT5 terminal64.exe not found. Cannot run physical backtest for {module_name}.")

    # 1. Compile the actual child EA (idempotent; console usually compiled it already)
    ea_path = PROJECT_ROOT / "ea" / f"{module_name}.mq5"
    compile_ok, compile_log = write_and_compile_mql5(ea_path, mql5_code)
    if not compile_ok:
        raise RuntimeError(f"EA {module_name} failed to compile inside backtest runner: {compile_log[:400]}")

    # 2. Run the physical MT5 Strategy Tester (zero-tolerance: raises if no report).
    #    params = genetic-optimization winners, injected as [TesterInputs] overrides.
    report_path = run_mt5_backtest(ea_name=module_name, module_name=module_name, input_overrides=params)

    # 3. Scrape ground-truth metrics from the physical HTML report
    metrics = parse_mt5_report(report_path)

    # 4. Extract real per-trade round trips from the report's Deals table.
    #    The console feeds the losers into the next iteration's forensic diagnosis.
    trades_df = parse_mt5_trades(report_path)

    return metrics, trades_df, report_path
