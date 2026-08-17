"""
StratX Tier-3: Skill Lifecycle & Curation Registry (skill_lifecycle.py)
Implements the MUSE-Autoskill / SkillOS concepts as a deterministic registry:

  Executor (Self-Healer) USES skills during a mission — it never rewrites them.
  Curator (this registry + offline SkillOpt) owns skill health across missions.

Every skill is a long-lived object:
  SKILL_ID, VERSION, CREATED_FROM, USE_COUNT, MISSIONS_USED,
  SUCCESSFUL_USES, FAILED_USES, KNOWN_GOOD_CONTEXTS, KNOWN_BAD_CONTEXTS,
  EVIDENCE, REGRESSIONS, CURRENT_SCORE,
  STATUS: EXPERIMENTAL -> VALIDATED -> PRODUCTION -> DEGRADED -> RETIRED

Curator actions (CREATE / MERGE / SPLIT / MODIFY / DEPRECATE / RETIRE) are
PROPOSALS ONLY. Promotion requires the SkillOpt gate: replay benchmark +
held-out validation + regression pass. Nothing self-modifies mid-mission.
"""

import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

REGISTRY_FILE = Path("C:/Trading/DE40-Research/stratx_brain/skill_registry.json")

SKILL_STATUSES = ["EXPERIMENTAL", "VALIDATED", "PRODUCTION", "DEGRADED", "RETIRED"]
CURATOR_ACTIONS = ["CREATE", "MERGE", "SPLIT", "MODIFY", "DEPRECATE", "RETIRE"]

# Promotion gates (deterministic): a skill earns status; it is never granted.
PROMOTION_GATES = {
    "VALIDATED":   {"min_uses": 3,  "min_score": 0.55},
    "PRODUCTION":  {"min_uses": 8,  "min_score": 0.70},
}
DEGRADED_SCORE = 0.35  # below this a PRODUCTION/VALIDATED skill auto-degrades


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class SkillLifecycleRegistry:
    """Append-friendly JSON registry. The curator proposes; the gate disposes."""

    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = Path(registry_file) if registry_file else REGISTRY_FILE
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.proposals: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.registry_file.exists():
            try:
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                self.skills = data.get("skills", {})
                self.proposals = data.get("proposals", [])
            except Exception:
                self.skills, self.proposals = {}, []

    def _save(self):
        tmp = self.registry_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"skills": self.skills, "proposals": self.proposals}, indent=2), encoding="utf-8")
        if self.registry_file.exists():
            self.registry_file.unlink()
        tmp.rename(self.registry_file)

    # ---------------- Skill lifecycle ----------------
    def register_skill(self, skill_id: str, created_from: str = "MANUAL", initial_contexts: Optional[List[str]] = None) -> Dict[str, Any]:
        if skill_id in self.skills:
            return self.skills[skill_id]
        rec = {
            "skill_id": skill_id,
            "version": "1.0",
            "created_from": created_from,
            "use_count": 0,
            "missions_used": [],
            "successful_uses": 0,
            "failed_uses": 0,
            "known_good_contexts": list(initial_contexts or []),
            "known_bad_contexts": [],
            "evidence": [],
            "regressions": [],
            "current_score": 0.50,
            "status": "EXPERIMENTAL",
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.skills[skill_id] = rec
        self._save()
        return rec

    def record_use(self, skill_id: str, mission_id: str, success: bool, context: str,
                   evidence_id: Optional[str] = None, evidence_weight: float = 1.0) -> Dict[str, Any]:
        """Record one executor use. Score movement is evidence-weighted."""
        rec = self.skills.get(skill_id) or self.register_skill(skill_id)
        w = max(0.10, min(1.50, float(evidence_weight)))
        rec["use_count"] += 1
        if mission_id not in rec["missions_used"]:
            rec["missions_used"].append(mission_id)
        if success:
            rec["successful_uses"] += 1
            rec["current_score"] = min(1.0, round(rec["current_score"] + 0.05 * w, 3))
            if context and context not in rec["known_good_contexts"]:
                rec["known_good_contexts"].append(context)
        else:
            rec["failed_uses"] += 1
            rec["current_score"] = max(0.0, round(rec["current_score"] - 0.08 * w, 3))
            if context and context not in rec["known_bad_contexts"]:
                rec["known_bad_contexts"].append(context)
        if evidence_id:
            rec["evidence"].append({"evidence_id": evidence_id, "success": success, "ts": _now()})
        rec["status"] = self._evaluate_status(rec)
        rec["updated_at"] = _now()
        self._save()
        return rec

    def _evaluate_status(self, rec: Dict[str, Any]) -> str:
        if rec["status"] == "RETIRED":
            return "RETIRED"
        score, uses = rec["current_score"], rec["use_count"]
        if score < DEGRADED_SCORE and rec["status"] in ("VALIDATED", "PRODUCTION"):
            return "DEGRADED"
        for target in ("PRODUCTION", "VALIDATED"):  # highest first
            gate = PROMOTION_GATES[target]
            if uses >= gate["min_uses"] and score >= gate["min_score"]:
                return target
        return "EXPERIMENTAL"

    # ---------------- Curator (SkillOS separation) ----------------
    def propose_curation(self, action: str, rationale: str, target_skill_ids: List[str],
                         proposed_by: str = "META_CURATOR") -> Dict[str, Any]:
        """Curator proposes; nothing is applied until the SkillOpt gate passes."""
        if action not in CURATOR_ACTIONS:
            raise ValueError(f"Unknown curator action: {action}")
        proposal = {
            "proposal_id": f"CUR_{uuid.uuid4().hex[:8].upper()}",
            "action": action,
            "rationale": rationale,
            "target_skill_ids": target_skill_ids,
            "proposed_by": proposed_by,
            "status": "PENDING_SKILLOPT_VALIDATION",
            "created_at": _now(),
        }
        self.proposals.append(proposal)
        self._save()
        return proposal

    def validate_and_apply(self, proposal_id: str, replay_passed: bool, held_out_passed: bool,
                           regression_passed: bool) -> Dict[str, Any]:
        """SkillOpt gate: replay + held-out + regression. All three required."""
        prop = next((p for p in self.proposals if p["proposal_id"] == proposal_id), None)
        if not prop:
            raise KeyError(proposal_id)
        if prop["status"] != "PENDING_SKILLOPT_VALIDATION":
            return prop
        if not (replay_passed and held_out_passed and regression_passed):
            prop["status"] = "REJECTED"
            prop["reject_reason"] = f"replay={replay_passed} held_out={held_out_passed} regression={regression_passed}"
            self._save()
            return prop
        prop["status"] = "APPLIED"
        for sid in prop["target_skill_ids"]:
            rec = self.skills.get(sid)
            if not rec:
                continue
            if prop["action"] in ("DEPRECATE", "RETIRE"):
                rec["status"] = "RETIRED" if prop["action"] == "RETIRE" else "DEGRADED"
            elif prop["action"] == "MODIFY":
                major, _, minor = rec["version"].partition(".")
                rec["version"] = f"{major}.{int(minor or 0) + 1}"
                rec["status"] = "EXPERIMENTAL"  # modified skills must re-earn promotion
            rec["regressions"].append({"proposal_id": proposal_id, "ts": _now(), "result": "PASS"})
            rec["updated_at"] = _now()
        self._save()
        return prop

    def discover_skill_gap(self, recurring_problem: str, occurrences: int, min_occurrences: int = 3) -> Optional[Dict[str, Any]]:
        """Skill discovery: after enough recurrences with no fitting skill, propose CREATE."""
        if occurrences < min_occurrences:
            return None
        return self.propose_curation(
            action="CREATE",
            rationale=f"Recurring problem with no appropriate skill ({occurrences}x): {recurring_problem}",
            target_skill_ids=[],
        )
