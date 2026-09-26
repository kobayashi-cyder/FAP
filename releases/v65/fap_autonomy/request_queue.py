from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


class SkillFactoryRequestQueue:
    """Filesystem handoff that never imports or executes generated code."""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def enqueue(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        if spec.get("metadata", {}).get("executable", True):
            raise ValueError("Only non-executable capability specifications may be queued")
        canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        capability_id = str(spec.get("capability_id", "unknown")).replace("/", "_").replace("\\", "_")
        final = self.directory / f"{capability_id}__{digest[:16]}.json"
        if final.exists():
            return {"queued": False, "duplicate": True, "path": str(final), "sha256": digest}
        fd, tmp = tempfile.mkstemp(prefix=".tmp-fap-", suffix=".json", dir=str(self.directory))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(canonical)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, final)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {"queued": True, "duplicate": False, "path": str(final), "sha256": digest}
