from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .promotion_ledger import digest_tree


class ActivationError(ValueError):
    pass


def _atomic_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class AtomicActivationManager:
    """Activation by manifest pointer only; never imports generated code."""

    def __init__(self, active_manifest: str, history_dir: str):
        self.active_manifest = Path(active_manifest)
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def current(self) -> Optional[Dict[str, Any]]:
        if not self.active_manifest.exists():
            return None
        return json.loads(self.active_manifest.read_text(encoding="utf-8"))

    def activate(self, *, capability_id: str, artifact: Dict[str, Any], registry_entry: Dict[str, Any], source_release: str = "v63") -> Dict[str, Any]:
        evidence = registry_entry.get("evidence") or {}
        lifecycle = evidence.get("lifecycle") or {}
        if lifecycle.get("state") != "consolidated":
            raise ActivationError("registry entry is not consolidated")
        expected = registry_entry.get("candidate_digest") or evidence.get("candidate_digest")
        candidate_dir = str(Path(artifact.get("candidate_dir", "")).resolve())
        if not Path(candidate_dir).is_dir():
            raise ActivationError("candidate_dir missing")
        actual = digest_tree(candidate_dir)
        if not expected or actual != expected:
            raise ActivationError("candidate digest mismatch")
        prev = self.current()
        now = time.time()
        record = {
            "schema": 1,
            "capability_id": capability_id,
            "candidate_digest": actual,
            "candidate_dir": candidate_dir,
            "activated_at": now,
            "source_release": source_release,
            "previous": {
                "capability_id": prev.get("capability_id"),
                "candidate_digest": prev.get("candidate_digest"),
                "candidate_dir": prev.get("candidate_dir"),
            } if prev else None,
        }
        if prev:
            _atomic_json(self.history_dir / f"{int(now * 1000)}_previous.json", prev)
        _atomic_json(self.active_manifest, record)
        return record

    def rollback(self, *, reason: str) -> Dict[str, Any]:
        cur = self.current()
        if not cur:
            raise ActivationError("nothing active")
        previous = cur.get("previous")
        if not previous or not previous.get("candidate_dir"):
            raise ActivationError("no previous activation available")
        prev_dir = Path(previous["candidate_dir"])
        if not prev_dir.is_dir():
            raise ActivationError("previous candidate_dir missing")
        actual = digest_tree(str(prev_dir.resolve()))
        if actual != previous.get("candidate_digest"):
            raise ActivationError("previous candidate digest mismatch")
        rolled = {
            "schema": 1,
            "capability_id": previous.get("capability_id"),
            "candidate_digest": actual,
            "candidate_dir": str(prev_dir.resolve()),
            "activated_at": time.time(),
            "source_release": "rollback",
            "rollback_reason": str(reason),
            "rolled_back_from": {k: cur.get(k) for k in ("capability_id", "candidate_digest", "candidate_dir", "activated_at")},
            "previous": None,
        }
        _atomic_json(self.active_manifest, rolled)
        return rolled
