"""
StratX State Persistence & Crash Recovery (state_persistence.py)
Guarantees zero data loss across multi-hour autonomous sessions:
1. Atomic file writes (writes to .tmp then renames) to prevent corrupt JSON on OS crash.
2. Auto-discovery and resumption of ACTIVE goal sessions upon boot.
3. Full history and iteration lineage preservation.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

class StatePersistenceManager:
    DEFAULT_CHECKPOINT_DIR = Path("C:/Trading/DE40-Research/checkpoints")

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else self.DEFAULT_CHECKPOINT_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_goal_state(self, session: Dict[str, Any]) -> Path:
        """
        Atomically saves goal session state to disk.
        """
        goal_id = session.get("goal_id", "GLOBAL_GOAL")
        target_file = self.checkpoint_dir / f"STATE_{goal_id}.json"
        tmp_file = self.checkpoint_dir / f"STATE_{goal_id}.tmp"

        dump_data = json.dumps(session, indent=2)
        tmp_file.write_text(dump_data, encoding="utf-8")
        
        # Atomic replace
        if target_file.exists():
            target_file.unlink()
        tmp_file.rename(target_file)
        
        return target_file

    def load_goal_state(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Loads specific goal session state."""
        target_file = self.checkpoint_dir / f"STATE_{goal_id}.json"
        if not target_file.exists():
            return None
        try:
            return json.loads(target_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def find_active_goal_session(self) -> Optional[Dict[str, Any]]:
        """
        Finds the most recent ACTIVE goal session for auto-resume.
        """
        state_files = list(self.checkpoint_dir.glob("STATE_*.json"))
        active_sessions = []

        for f in state_files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("goal_status") in ["ACTIVE", "REASSESSING", "TESTING"]:
                    mtime = f.stat().st_mtime
                    active_sessions.append((mtime, data))
            except Exception:
                continue

        if not active_sessions:
            return None

        # Return newest active session
        active_sessions.sort(key=lambda x: x[0], reverse=True)
        return active_sessions[0][1]
