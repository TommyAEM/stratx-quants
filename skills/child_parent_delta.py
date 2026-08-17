"""
StratX Quant Skill 7: Child-Parent Trade Delta Engine
Performs position-by-position matching between Parent and Child populations.
Explains WHY performance changed (Same, Removed, New, Loser->Winner, Winner->Loser, MAE/MFE deltas).
"""

from typing import Dict, Any, List, Optional

class ChildParentDelta:
    def __init__(self, match_time_tolerance_sec: int = 300):
        self.match_time_tolerance_sec = match_time_tolerance_sec

    def compute_delta(self, parent_positions: List[Dict[str, Any]], child_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes granular trade population differences between parent and child.
        """
        parent_map = {self._trade_key(p): p for p in parent_positions}
        child_map = {self._trade_key(c): c for c in child_positions}

        same_trades = []
        removed_trades = []
        new_trades = []

        loser_to_winner = []
        winner_to_loser = []
        winner_removed = []
        loser_removed = []

        # Compare Parent vs Child
        for k, p in parent_map.items():
            p_win = p.get("trade_R", 0) > 0
            if k in child_map:
                c = child_map[k]
                c_win = c.get("trade_R", 0) > 0
                same_trades.append({
                    "trade_key": k,
                    "parent_R": p.get("trade_R", 0),
                    "child_R": c.get("trade_R", 0),
                    "R_delta": round(c.get("trade_R", 0) - p.get("trade_R", 0), 4),
                    "parent_mae": p.get("MAE", 0),
                    "child_mae": c.get("MAE", 0)
                })
                if not p_win and c_win:
                    loser_to_winner.append(k)
                elif p_win and not c_win:
                    winner_to_loser.append(k)
            else:
                removed_trades.append(p)
                if p_win:
                    winner_removed.append(k)
                else:
                    loser_removed.append(k)

        for k, c in child_map.items():
            if k not in parent_map:
                new_trades.append(c)

        parent_n = len(parent_positions)
        child_n = len(child_positions)
        parent_net_r = sum(p.get("trade_R", 0) for p in parent_positions)
        child_net_r = sum(c.get("trade_R", 0) for c in child_positions)

        parent_wr = sum(1 for p in parent_positions if p.get("trade_R", 0) > 0) / max(1, parent_n)
        child_wr = sum(1 for c in child_positions if c.get("trade_R", 0) > 0) / max(1, child_n)

        # Causal classification of improvement
        causal_interpretation = "NEUTRAL"
        if child_net_r > parent_net_r:
            if len(loser_removed) > len(winner_removed) * 2:
                causal_interpretation = "IMPROVEMENT_VIA_LOSER_ELIMINATION (Successfully pruned bad trade cohort)"
            elif len(loser_to_winner) > 0:
                causal_interpretation = "IMPROVEMENT_VIA_EXECUTION_ENHANCEMENT (Converted losers into winners)"
            elif len(new_trades) > 0 and sum(c.get("trade_R", 0) for c in new_trades) > 0:
                causal_interpretation = "IMPROVEMENT_VIA_NEW_ALPHA_OPPORTUNITIES (New valid entries added)"
            else:
                causal_interpretation = "IMPROVEMENT_UNCLEAR (Requires further attribution check)"
        elif child_net_r < parent_net_r:
            if len(winner_removed) > len(loser_removed):
                causal_interpretation = "DEGRADATION_VIA_WINNER_DESTRUCTION (Filter pruned high-value winners)"
            else:
                causal_interpretation = "DEGRADATION_VIA_ADVERSE_MUTATION"

        return {
            "parent_trade_count": parent_n,
            "child_trade_count": child_n,
            "trade_count_delta": child_n - parent_n,
            "frequency_retention_pct": round((child_n / max(1, parent_n)) * 100.0, 2),
            "parent_win_rate": round(parent_wr, 4),
            "child_win_rate": round(child_wr, 4),
            "parent_net_R": round(parent_net_r, 4),
            "child_net_R": round(child_net_r, 4),
            "net_R_delta": round(child_net_r - parent_net_r, 4),
            "same_trade_count": len(same_trades),
            "removed_trade_count": len(removed_trades),
            "new_trade_count": len(new_trades),
            "losers_removed_count": len(loser_removed),
            "winners_removed_count": len(winner_removed),
            "loser_to_winner_count": len(loser_to_winner),
            "winner_to_loser_count": len(winner_to_loser),
            "causal_interpretation": causal_interpretation,
            "net_beneficial_filter": bool(len(loser_removed) > 0 and len(winner_removed) == 0)
        }

    def _trade_key(self, pos: Dict[str, Any]) -> str:
        t = str(pos.get("entry_time", "")).replace(" ", "_")
        d = str(pos.get("direction", "")).upper()
        p = str(round(float(pos.get("entry_price", 0.0)), 2))
        return f"{t}_{d}_{p}"
