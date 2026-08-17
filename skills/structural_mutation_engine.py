"""
StratX Quant Skill 8: Structural Mutation Engine & Implementation Validator
Consumes canonical EXPERIMENT_SPEC, validates structural changes across Levels 1-5,
and compares EXPERIMENT_SPEC against IMPLEMENTATION_RECEIPT before MT5 run.
"""

from typing import Dict, Any, List, Optional
import hashlib
import json

class StructuralMutationEngine:
    VALID_REPAIR_LEVELS = ["L1_PARAMETER", "L2_RULE", "L3_COMPONENT", "L4_ARCHITECTURE", "L5_FAMILY"]

    def create_experiment_spec(self, experiment_id: str, parent_strategy_id: str, hypothesis_id: str, repair_level: str, market_thesis: str, parameter_changes: Dict[str, Any], entry_logic_change: str = "", exit_logic_change: str = "") -> Dict[str, Any]:
        """
        Creates an immutable, canonical Experiment Specification.
        """
        if repair_level not in self.VALID_REPAIR_LEVELS:
            raise ValueError(f"Invalid repair level: {repair_level}. Must be one of {self.VALID_REPAIR_LEVELS}")

        spec = {
            "experiment_id": experiment_id,
            "parent_strategy_id": parent_strategy_id,
            "hypothesis_id": hypothesis_id,
            "repair_level": repair_level,
            "market_thesis": market_thesis,
            "entry_architecture_change": entry_logic_change,
            "exit_architecture_change": exit_logic_change,
            "parameter_changes": parameter_changes,
            "spec_hash": ""
        }
        raw_bytes = json.dumps(spec, sort_keys=True).encode("utf8")
        spec["spec_hash"] = hashlib.sha256(raw_bytes).hexdigest()[:16]
        return spec

    def create_implementation_receipt(self, experiment_id: str, source_path: str, source_content: str, set_content: str, implemented_params: Dict[str, Any], compile_success: bool = True) -> Dict[str, Any]:
        """
        Generates an immutable implementation receipt from compiled MQL5/SET code.
        """
        source_hash = hashlib.sha256(source_content.encode("utf8")).hexdigest()[:16]
        set_hash = hashlib.sha256(set_content.encode("utf8")).hexdigest()[:16]

        receipt = {
            "experiment_id": experiment_id,
            "source_path": source_path,
            "source_hash": source_hash,
            "set_hash": set_hash,
            "implemented_parameters": implemented_params,
            "compile_success": compile_success
        }
        return receipt

    def validate_implementation(self, spec: Dict[str, Any], receipt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministically verifies that the code matches the Experiment Spec.
        """
        mismatches = []

        if spec.get("experiment_id") != receipt.get("experiment_id"):
            mismatches.append(f"Experiment ID mismatch: {spec.get('experiment_id')} vs {receipt.get('experiment_id')}")

        if not receipt.get("compile_success", False):
            mismatches.append("MQL5 Compilation failed.")

        # Check required parameter changes
        req_params = spec.get("parameter_changes", {})
        imp_params = receipt.get("implemented_parameters", {})

        for p_name, p_val in req_params.items():
            if p_name not in imp_params:
                mismatches.append(f"Missing required parameter in implementation: {p_name}")
            elif str(imp_params[p_name]) != str(p_val):
                mismatches.append(f"Parameter value mismatch for {p_name}: expected {p_val}, got {imp_params[p_name]}")

        is_valid = (len(mismatches) == 0)

        return {
            "status": "APPROVED" if is_valid else "IMPLEMENTATION_FAILURE",
            "is_valid": is_valid,
            "mismatches": mismatches,
            "spec_hash": spec.get("spec_hash", ""),
            "receipt_source_hash": receipt.get("source_hash", "")
        }
