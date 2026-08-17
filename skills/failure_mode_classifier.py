"""
StratX Quant Skill 5: Failure Mode Taxonomy & Classifier
Classifies strategy failures into an extensible 20-category taxonomy,
tracks historically attempted interventions, outcomes, and empirical confidence.
"""

from typing import Dict, Any, List, Optional
import json

class FailureModeClassifier:
    CANONICAL_TAXONOMY = [
        "REGIME_MISMATCH",
        "NEWS_EVENT_SHOCK",
        "LIQUIDITY_SPREAD_PATHOLOGY",
        "SESSION_PATHOLOGY",
        "PARAMETER_FRAGILITY",
        "CORRELATION_BREAKDOWN",
        "EXECUTION_DECAY",
        "ENTRY_ARCHITECTURE_FAILURE",
        "EXIT_ARCHITECTURE_FAILURE",
        "STOP_ARCHITECTURE_FAILURE",
        "DIRECTIONAL_BIAS_FAILURE",
        "FREQUENCY_COLLAPSE",
        "FILTER_ACCRETION",
        "OVERFITTING_DECAY",
        "DATA_QUALITY_FAILURE",
        "TELEMETRY_FAILURE",
        "ACCOUNTING_FAILURE",
        "IMPLEMENTATION_FAILURE",
        "VALIDATION_COLLAPSE",
        "UNKNOWN_FAILURE"
    ]

    def __init__(self, history_store: Optional[Dict[str, Any]] = None):
        self.history = history_store or {}

    def classify_failure(self, failure_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies an observed strategy failure into one or more taxonomy categories.
        """
        classification = []
        evidence_notes = []

        dev_pf = float(failure_evidence.get("dev_pf", 1.0))
        val_pf = float(failure_evidence.get("val_pf", 1.0))
        freq_drop = float(failure_evidence.get("trade_drop_pct", 0.0))
        spread_sens = bool(failure_evidence.get("spread_sensitive", False))
        telemetry_err = bool(failure_evidence.get("telemetry_defect", False))
        accounting_err = bool(failure_evidence.get("accounting_discrepancy", False))
        long_wr = float(failure_evidence.get("long_wr", 0.5))
        short_wr = float(failure_evidence.get("short_wr", 0.5))
        rule_count = int(failure_evidence.get("rules_added_count", 0))

        # 1. Telemetry / Accounting Failures
        if telemetry_err:
            classification.append("TELEMETRY_FAILURE")
            evidence_notes.append("Feature calculation or bar indexing defect detected in data/telemetry feed.")
        if accounting_err:
            classification.append("ACCOUNTING_FAILURE")
            evidence_notes.append("Reconstructed PF does not match reported PF.")

        # 2. Validation Collapse & Overfit
        if dev_pf >= 2.0 and val_pf < 1.05:
            classification.append("VALIDATION_COLLAPSE")
            classification.append("OVERFITTING_DECAY")
            evidence_notes.append(f"DEV PF ({dev_pf}) collapsed on Out-of-Sample VAL ({val_pf}).")

        # 3. Filter Accretion & Frequency Collapse
        if rule_count >= 3 and freq_drop >= 40.0:
            classification.append("FILTER_ACCRETION")
            classification.append("FREQUENCY_COLLAPSE")
            evidence_notes.append(f"Heavy rule stacking ({rule_count} rules) eliminated {freq_drop}% of trade population.")

        # 4. Directional Bias
        if abs(long_wr - short_wr) >= 0.35 and (long_wr < 0.35 or short_wr < 0.35):
            classification.append("DIRECTIONAL_BIAS_FAILURE")
            evidence_notes.append(f"Severe directional asymmetry: Long WR {long_wr} vs Short WR {short_wr}.")

        # 5. Liquidity / Spread Pathology
        if spread_sens:
            classification.append("LIQUIDITY_SPREAD_PATHOLOGY")
            evidence_notes.append("Edge vanishes under realistic broker spread / execution slippage stress.")

        if not classification:
            classification.append("UNKNOWN_FAILURE")
            evidence_notes.append("Failure does not match predefined automated triggers; deep manual analysis required.")

        primary_mode = classification[0]

        # Retrieve historically attempted interventions
        past_interventions = self.history.get(primary_mode, [])

        return {
            "primary_failure_mode": primary_mode,
            "all_categories": classification,
            "evidence_notes": evidence_notes,
            "historical_interventions": past_interventions,
            "recommended_next_action": self._suggest_action(primary_mode)
        }

    def _suggest_action(self, mode: str) -> str:
        suggestions = {
            "TELEMETRY_FAILURE": "QUARANTINE_EVIDENCE_AND_RERUN_BASELINE",
            "ACCOUNTING_FAILURE": "REBUILD_CANONICAL_TRADE_POPULATION",
            "VALIDATION_COLLAPSE": "REVERT_GATES_TO_PARENT_AND_EXPLORE_ARCHITECTURAL_HEALING",
            "FILTER_ACCRETION": "ABLATE_FILTERS_AND_REVIEW_CORE_ENTRY_ALPHA",
            "DIRECTIONAL_BIAS_FAILURE": "SEPARATE_LONG_SHORT_ENGINES_OR_RESTRICT_TO_FAVORED_REGIME",
            "LIQUIDITY_SPREAD_PATHOLOGY": "WIDEN_TARGET_GEOMETRY_OR_APPLY_SPREAD_FILTER",
            "UNKNOWN_FAILURE": "FORMULATE_COMPETING_HYPOTHESES_H1_TO_HN"
        }
        return suggestions.get(mode, "FORMULATE_COMPETING_HYPOTHESES")

    def record_intervention(self, failure_mode: str, intervention: str, outcome: str, confidence: float):
        if failure_mode not in self.history:
            self.history[failure_mode] = []
        self.history[failure_mode].append({
            "intervention": intervention,
            "outcome": outcome,
            "confidence": round(confidence, 2)
        })
