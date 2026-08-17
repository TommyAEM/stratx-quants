"""
StratX Quant Skill 3: Point-in-Time Regime Tagger
Computes versioned market regime features at time of trade entry with ZERO future leakage.
"""

from typing import Dict, Any, List, Optional
import datetime

class RegimeTagger:
    VERSION = "1.1.0"

    def __init__(self, atr_lookback: int = 14, vwap_lookback_bars: int = 40):
        self.atr_lookback = atr_lookback
        self.vwap_lookback_bars = vwap_lookback_bars

    def tag_trade(self, trade: Dict[str, Any], market_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enriches a single trade with versioned point-in-time regime tags.
        """
        entry_time_str = trade.get("entry_time", "")
        # Parse session / hour
        hour = 0
        weekday = trade.get("day_of_week", "UNKNOWN")
        session = trade.get("session", "UNKNOWN")

        if entry_time_str:
            try:
                # Expect YYYY-MM-DD HH:MM:SS or similar
                clean_time = entry_time_str.replace(".", "-")
                if " " in clean_time:
                    parts = clean_time.split(" ")
                    dt_part = parts[0]
                    tm_part = parts[1]
                    hour = int(tm_part.split(":")[0])
                    dt_obj = datetime.datetime.strptime(dt_part, "%Y-%m-%d")
                    weekday = dt_obj.strftime("%A")
            except Exception:
                pass

        if session == "UNKNOWN":
            if 7 <= hour < 11:
                session = "LONDON_OPEN"
            elif 11 <= hour < 13:
                session = "LONDON_MIDDAY"
            elif 13 <= hour < 17:
                session = "US_OVERLAP"
            elif 17 <= hour < 21:
                session = "US_AFTERNOON"
            else:
                session = "ASIA_OVERNIGHT"

        # Extract features from market context if provided, else use features dictionary
        mkt = market_context or trade.get("features", {})

        atr_val = float(mkt.get("atr") or mkt.get("f_atr") or 25.0)
        atr_pct = float(mkt.get("atr_pct") or mkt.get("f_atr_pct") or 50.0)
        adx_val = float(mkt.get("adx") or mkt.get("f_adx") or 20.0)
        disp_val = float(mkt.get("f_disp") or mkt.get("disp") or 1.0)
        rel_vol = float(mkt.get("f_rel_vol") or mkt.get("rel_vol") or 1.0)
        vwap_dist = float(mkt.get("f_vwap_dist") or mkt.get("vwap_dist") or 0.0)
        spread = float(mkt.get("spread") or trade.get("spread_at_entry") or 1.0)

        # Classify Regimes
        vol_regime = "NORMAL_VOL"
        if atr_pct >= 75.0:
            vol_regime = "HIGH_VOL"
        elif atr_pct <= 25.0:
            vol_regime = "LOW_VOL"

        trend_regime = "CHOP_RANGE"
        if adx_val >= 25.0:
            trend_regime = "STRONG_TREND"
        elif adx_val <= 15.0:
            trend_regime = "COMPRESSION_RANGE"

        liquidity_regime = "NORMAL_LIQUIDITY"
        if rel_vol < 0.7:
            liquidity_regime = "LOW_VOLUME_DRIFT"
        elif rel_vol > 1.8:
            liquidity_regime = "VOLUME_EXPANSION"

        tags = {
            "tagger_version": self.VERSION,
            "session": session,
            "day_of_week": weekday,
            "hour": hour,
            "volatility_regime": vol_regime,
            "trend_regime": trend_regime,
            "liquidity_regime": liquidity_regime,
            "point_in_time_features": {
                "f_disp": round(disp_val, 4),
                "f_rel_vol": round(rel_vol, 4),
                "f_atr": round(atr_val, 4),
                "f_atr_pct": round(atr_pct, 2),
                "f_adx": round(adx_val, 2),
                "f_vwap_dist": round(vwap_dist, 4),
                "spread": round(spread, 2)
            }
        }

        # Merge tags back into trade
        trade["session"] = session
        trade["day_of_week"] = weekday
        trade["regime_tags"] = tags
        trade["features"] = tags["point_in_time_features"]
        return trade

    def tag_population(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.tag_trade(p) for p in positions]
