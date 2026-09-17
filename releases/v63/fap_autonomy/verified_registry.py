from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


class VerifiedSkillRegistry:
    """Atomic manifest registry. Registration does not import/execute candidate code."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"schema": 1, "entries": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, capability_id: str) -> Optional[Dict[str, Any]]:
        return self._load().get("entries", {}).get(capability_id)

    def register_verified(self, capability_id: str, artifact: Dict[str, Any], evidence: Dict[str, Any]) -> bool:
        lifecycle = evidence.get("lifecycle") or {}
        if lifecycle.get("state") != "consolidated":
            return False
        candidate_digest = evidence.get("candidate_digest")
        if not candidate_digest:
            return False
        data = self._load()
        entries = data.setdefault("entries", {})
        entries[capability_id] = {
            "capability_id": capability_id,
            "candidate_digest": candidate_digest,
            "candidate_dir": str(artifact.get("candidate_dir", "")),
            "registered_at": time.time(),
            "activation": "manual_or_existing_registry_bridge",
            "evidence": evidence,
        }
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True
