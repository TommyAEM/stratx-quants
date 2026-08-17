"""
StratX Quant Skill 13: Research Map & Expected Information Value (EIV) Engine
Tracks exploration coverage across entry/exit/regimes/indicators and ranks
candidate research experiments by Expected Information Value.
"""

from typing import Dict, Any, List, Optional
import math

class ResearchMapEIVEngine:
    COVERAGE_LEVELS = ["UNEXPLORED", "LIGHT", "PARTIAL", "DEEP", "EXHAUSTED"]

    def __init__(self):
        self.territories: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_map()

    def _initialize_default_map(self):
        default_entries = [
            {"family": "VPPOC", "sub": "POC_REJECTION", "regime": "DEV_VAL", "coverage": "DEEP"},
            {"family": "FORB", "sub": "FAILED_ORB_REVERSAL", "regime": "DEV_VAL", "coverage": "EXHAUSTED"},
            {"family": "VWAPX", "sub": "VWAP_EXTENSION_REVERSION", "regime": "UNEXPLORED", "coverage": "LIGHT"},
            {"family": "LRF", "sub": "LONDON_RANGE_FAILURE", "regime": "UNEXPLORED", "coverage": "UNEXPLORED"},
            {"family": "BRKRT", "sub": "US_OVERLAP_CONTINUATION", "regime": "DEV_VAL", "coverage": "PARTIAL"},
            {"family": "SHEX", "sub": "SHORT_EXHAUSTION_M30", "regime": "UNEXPLORED", "coverage": "UNEXPLORED"}
        ]
        for item in default_entries:
            key = f"{item['family']}_{item['sub']}"
            self.territories[key] = item

    def update_territory(self, family: str, sub: str, coverage: str, notes: str = ""):
        if coverage not in self.COVERAGE_LEVELS:
            raise ValueError(f"Invalid coverage level: {coverage}")
        key = f"{family}_{sub}"
        if key not in self.territories:
            self.territories[key] = {"family": family, "sub": sub}
        self.territories[key]["coverage"] = coverage
        self.territories[key]["notes"] = notes

    def compute_eiv(self, candidate: Dict[str, Any]) -> float:
        """
        Computes Expected Information Value:
        EIV = (Brain Evidence * 0.3) + (Unexploredness * 0.3) + (Portfolio Gap Fill * 0.25) - (Prior Neg Penalty * 0.15)
        """
        brain_ev = float(candidate.get("brain_evidence", 0.5))
        coverage = str(candidate.get("coverage", "UNEXPLORED"))
        portfolio_gap = float(candidate.get("portfolio_gap_score", 0.5))
        neg_penalty = float(candidate.get("negative_prior_penalty", 0.0))

        unexplored_score = 1.0
        if coverage == "LIGHT":
            unexplored_score = 0.75
        elif coverage == "PARTIAL":
            unexplored_score = 0.50
        elif coverage == "DEEP":
            unexplored_score = 0.20
        elif coverage == "EXHAUSTED":
            unexplored_score = 0.0

        eiv = (brain_ev * 0.30) + (unexplored_score * 0.30) + (portfolio_gap * 0.25) - (neg_penalty * 0.15)
        return round(max(0.0, eiv), 4)

    def rank_candidates(self, candidate_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for c in candidate_list:
            c["eiv_score"] = self.compute_eiv(c)
        return sorted(candidate_list, key=lambda x: x["eiv_score"], reverse=True)

    def get_map(self) -> List[Dict[str, Any]]:
        return list(self.territories.values())
