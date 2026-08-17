"""
StratX Quant Skill 12: Evidence Dependency Graph
Maintains end-to-end lineage across features, observations, hypotheses, experiments,
reports, reviewer decisions, and module freezes. Supports automatic cascade invalidation.
"""

from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
import datetime

class EvidenceDependencyGraph:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges_out: Dict[str, Set[str]] = defaultdict(set) # node -> dependents
        self.edges_in: Dict[str, Set[str]] = defaultdict(set)  # node -> dependencies

    def add_node(self, node_id: str, node_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        node_type: FEATURE, FORENSIC_OBSERVATION, HYPOTHESIS, EXPERIMENT, MT5_REPORT, REVIEW_VERDICT, BRAIN_LESSON, MODULE_FREEZE
        """
        self.nodes[node_id] = {
            "node_id": node_id,
            "node_type": node_type,
            "status": "VALID",
            "metadata": metadata or {},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "invalidation_reason": None
        }

    def add_dependency(self, parent_id: str, child_id: str):
        """
        child_id depends on parent_id (e.g. Experiment depends on Hypothesis)
        """
        if parent_id not in self.nodes:
            self.add_node(parent_id, "UNKNOWN")
        if child_id not in self.nodes:
            self.add_node(child_id, "UNKNOWN")

        self.edges_out[parent_id].add(child_id)
        self.edges_in[child_id].add(parent_id)

    def invalidate_node(self, root_node_id: str, cause: str) -> Dict[str, Any]:
        """
        Cascades invalidation down the dependency tree.
        Marks all descendants as INVALIDATED_<cause> or REQUIRES_RERUN.
        """
        if root_node_id not in self.nodes:
            return {"status": "NODE_NOT_FOUND", "invalidated_count": 0}

        invalidated = []
        queue = [root_node_id]
        visited = set()

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            node = self.nodes.get(curr)
            if node:
                node["status"] = f"INVALIDATED_{cause}"
                node["invalidation_reason"] = cause
                node["invalidated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                invalidated.append({
                    "node_id": curr,
                    "node_type": node["node_type"],
                    "new_status": node["status"]
                })

            for child in self.edges_out.get(curr, []):
                if child not in visited:
                    queue.append(child)

        return {
            "status": "CASCADED",
            "root_node": root_node_id,
            "cause": cause,
            "invalidated_count": len(invalidated),
            "affected_nodes": invalidated
        }

    def get_lineage(self, node_id: str) -> Dict[str, Any]:
        """
        Returns upstream ancestors and downstream descendants.
        """
        ancestors = []
        descendants = []

        # Upstream walk
        q_up = list(self.edges_in.get(node_id, []))
        v_up = set()
        while q_up:
            n = q_up.pop(0)
            if n not in v_up:
                v_up.add(n)
                ancestors.append(n)
                q_up.extend(list(self.edges_in.get(n, [])))

        # Downstream walk
        q_down = list(self.edges_out.get(node_id, []))
        v_down = set()
        while q_down:
            n = q_down.pop(0)
            if n not in v_down:
                v_down.add(n)
                descendants.append(n)
                q_down.extend(list(self.edges_out.get(n, [])))

        return {
            "node_id": node_id,
            "status": self.nodes.get(node_id, {}).get("status", "UNKNOWN"),
            "ancestors": ancestors,
            "descendants": descendants
        }
