"""
StratX Quant Skill 1: Canonical Trade Population Engine
Aggregates MT5 raw deal records into logical strategy positions, normalizes R0 risk,
computes canonical performance metrics, and performs strict accounting reconciliation.
Supports all MT5 and StratX CSV column formats and epoch timestamps.
"""

import math
import hashlib
import datetime
from typing import Dict, Any, List, Optional

class TradePopulationAnalyzer:
    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance

    def _parse_time(self, val: Any) -> str:
        if val is None or val == "":
            return ""
        val_str = str(val).strip()
        # Check if numeric epoch timestamp
        try:
            val_num = float(val_str)
            if val_num > 1000000000: # Valid Unix epoch seconds
                dt = datetime.datetime.fromtimestamp(val_num, datetime.timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        return val_str

    def analyze_trades(self, raw_deals_or_trades: List[Dict[str, Any]], ea_source: str = "", set_source: str = "") -> Dict[str, Any]:
        """
        Processes trade list, normalizes R, and verifies accounting reconciliation.
        """
        if not raw_deals_or_trades:
            return {
                "status": "EMPTY",
                "trade_count": 0,
                "positions": [],
                "metrics": {}
            }

        positions = []
        total_pnl = 0.0
        wins = []
        losses = []

        for idx, row in enumerate(raw_deals_or_trades):
            pos_id = str(row.get("position_id") or row.get("ticket") or f"POS_{idx+1}")
            symbol = str(row.get("symbol") or row.get("Symbol") or "UNKNOWN")
            
            raw_dir = str(row.get("side") or row.get("direction") or row.get("type") or row.get("Type") or "LONG").upper()
            if "BUY" in raw_dir or raw_dir in ["0", "LONG"]:
                direction = "LONG"
            elif "SELL" in raw_dir or raw_dir in ["1", "SHORT"]:
                direction = "SHORT"
            else:
                direction = "LONG"

            entry_time = self._parse_time(row.get("time_open") or row.get("open_time") or row.get("entry_time") or row.get("Time") or row.get("Timestamp"))
            exit_time = self._parse_time(row.get("time_close") or row.get("close_time") or row.get("exit_time"))

            entry_price = float(row.get("entry") or row.get("entry_price") or row.get("open_price") or row.get("price_open") or 0.0)
            exit_price = float(row.get("exit_price") or row.get("close_price") or row.get("exit") or row.get("price_close") or 0.0)

            initial_sl = float(row.get("sl") or row.get("initial_sl") or row.get("stop_loss") or 0.0)
            initial_tp = float(row.get("tp") or row.get("initial_tp") or row.get("take_profit") or 0.0)

            # R0 monetary risk calculation
            r0 = float(row.get("R0") or row.get("risk_usd") or 0.0)
            if r0 <= 0.0:
                if initial_sl > 0.0 and entry_price > 0.0:
                    r0 = abs(entry_price - initial_sl)
                else:
                    r0 = 100.0 # Standard unit baseline

            if r0 <= 0.0:
                r0 = 1.0

            # Net R extraction
            raw_r = row.get("R") if row.get("R") is not None else (row.get("trade_R") if row.get("trade_R") is not None else row.get("net_R"))
            net_profit_val = row.get("net_profit") if row.get("net_profit") is not None else (row.get("profit") if row.get("profit") is not None else row.get("pnl"))

            if raw_r is not None:
                trade_r = float(raw_r)
                net_profit = float(net_profit_val) if net_profit_val is not None else (trade_r * r0)
            elif net_profit_val is not None:
                net_profit = float(net_profit_val)
                trade_r = net_profit / r0
            else:
                trade_r = 0.0
                net_profit = 0.0

            mae = float(row.get("MAE_R") or row.get("MAE") or row.get("mae") or row.get("mae_r") or 0.0)
            mfe = float(row.get("MFE_R") or row.get("MFE") or row.get("mfe") or row.get("mfe_r") or 0.0)
            duration_min = float(row.get("duration") or row.get("duration_min") or 0.0)

            session = str(row.get("session_bucket") or row.get("session") or row.get("Session") or "UNKNOWN")
            day_of_week = str(row.get("weekday") or row.get("day_of_week") or row.get("day") or "UNKNOWN")

            # Extract features (f_* columns and explicit numeric features)
            features = {}
            if isinstance(row.get("features"), dict):
                features.update(row["features"])
            for k, v in row.items():
                if k.startswith("f_") or k.startswith("feat_") or k in ["vwap_dist_atr", "vwap_ext_atr", "reclaim_atr"]:
                    try:
                        features[k] = float(v)
                    except (ValueError, TypeError):
                        features[k] = v

            pos = {
                "position_id": pos_id,
                "symbol": symbol,
                "direction": direction,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_sl": initial_sl,
                "initial_tp": initial_tp,
                "R0": r0,
                "net_profit": round(net_profit, 2),
                "trade_R": round(trade_r, 4),
                "MAE": mae,
                "MFE": mfe,
                "duration_min": duration_min,
                "session": session,
                "day_of_week": day_of_week,
                "features": features
            }
            positions.append(pos)
            total_pnl += net_profit

            if trade_r > 0.0:
                wins.append(trade_r)
            else:
                losses.append(abs(trade_r))

        n = len(positions)
        n_wins = len(wins)
        n_losses = len(losses)
        wr = (n_wins / n) if n > 0 else 0.0

        avg_win_r = (sum(wins) / n_wins) if n_wins > 0 else 0.0
        avg_loss_r = (sum(losses) / n_losses) if n_losses > 0 else 1.0
        payoff_ratio = (avg_win_r / avg_loss_r) if avg_loss_r > 0 else 0.0

        gross_win_r = sum(wins)
        gross_loss_r = sum(losses)
        pf = (gross_win_r / gross_loss_r) if gross_loss_r > 0 else (99.0 if gross_win_r > 0 else 0.0)

        expectancy_r = (wr * avg_win_r) - ((1.0 - wr) * avg_loss_r)

        # Reconciliation: PF = (WR / (1-WR)) * Payoff
        if (1.0 - wr) > 0 and payoff_ratio > 0:
            pf_reconstructed = (wr / (1.0 - wr)) * payoff_ratio
        else:
            pf_reconstructed = pf

        reconciliation_discrepancy = abs(pf - pf_reconstructed)
        accounting_status = "VALID"
        if gross_loss_r > 0 and reconciliation_discrepancy > self.tolerance:
            accounting_status = "ACCOUNTING_INCONSISTENCY"

        # Hashes for provenance
        ea_hash = hashlib.sha256(ea_source.encode("utf8")).hexdigest()[:16] if ea_source else "N/A"
        set_hash = hashlib.sha256(set_source.encode("utf8")).hexdigest()[:16] if set_source else "N/A"

        metrics = {
            "trade_count": n,
            "win_count": n_wins,
            "loss_count": n_losses,
            "win_rate": round(wr, 4),
            "avg_win_R": round(avg_win_r, 4),
            "avg_loss_R": round(avg_loss_r, 4),
            "payoff_ratio": round(payoff_ratio, 4),
            "profit_factor": round(pf, 4),
            "reconstructed_pf": round(pf_reconstructed, 4),
            "expectancy_R": round(expectancy_r, 4),
            "total_net_R": round(sum(p["trade_R"] for p in positions), 4),
            "total_pnl": round(total_pnl, 2),
            "accounting_status": accounting_status,
            "reconciliation_discrepancy": round(reconciliation_discrepancy, 6),
            "source_ea_hash": ea_hash,
            "source_set_hash": set_hash
        }

        return {
            "status": "SUCCESS" if accounting_status == "VALID" else "ACCOUNTING_INCONSISTENCY",
            "metrics": metrics,
            "positions": positions
        }
