from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

_HEX = set("0123456789abcdef")


def _sha(value: str, field: str) -> str:
    text = str(value).lower().strip()
    if len(text) != 64 or any(c not in _HEX for c in text):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return text


class AndroidArtifactProvenanceWriter:
    """Additive schema-3 prototype; schema-1/2 writers remain untouched."""

    def __init__(self, out_path: str):
        self.out = Path(out_path)
        self.out.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        release: str,
        source_commit: str,
        release_manifest_sha256: str,
        verification_sha256: str,
        active_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        rel = str(release).strip()
        commit = str(source_commit).strip().lower()
        if not rel:
            raise ValueError("release is required")
        if len(commit) < 7 or any(c not in _HEX for c in commit):
            raise ValueError("source_commit must be a git hex SHA")
        data = {
            "schema": 3,
            "release": rel,
            "source_commit": commit,
            "release_manifest_sha256": _sha(release_manifest_sha256, "release_manifest_sha256"),
            "verification_sha256": _sha(verification_sha256, "verification_sha256"),
            "active": dict(active_state.get("active") or {}),
        }

        fd, tmp = tempfile.mkstemp(prefix=self.out.name + ".", dir=str(self.out.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.out)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return data
