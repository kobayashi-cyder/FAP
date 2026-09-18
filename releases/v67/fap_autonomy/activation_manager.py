from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .promotion_ledger import digest_tree
from .provenance import ProvenanceLedger


def _safe_name(value: str) -> str:
    out = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(value))
    if not out or out in {".", ".."}:
        raise ValueError("invalid capability_id")
    return out


class ActivationManager:
    """Stages verified skill snapshots and atomically switches an active manifest pointer.

    It never imports or executes candidate code. Runtime integration may load only the
    path selected by current(), after applying its own process/container boundary.
    """

    def __init__(self, root: str, *, provenance: Optional[ProvenanceLedger] = None):
        self.root = Path(root)
        self.slots = self.root / "slots"
        self.state_path = self.root / "active.json"
        self.slots.mkdir(parents=True, exist_ok=True)
        self.provenance = provenance or ProvenanceLedger(str(self.root / "provenance.jsonl"))

    def _load(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"schema": 1, "active": {}, "history": {}}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(prefix=self.state_path.name + ".", dir=str(self.root))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def stage_from_registry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        capability_id = str(entry.get("capability_id", ""))
        evidence = entry.get("evidence") or {}
        lifecycle = evidence.get("lifecycle") or {}
        if lifecycle.get("state") != "consolidated":
            raise ValueError("registry entry is not consolidated")
        expected = str(entry.get("candidate_digest") or evidence.get("candidate_digest") or "")
        if len(expected) != 64:
            raise ValueError("candidate digest missing")
        source = Path(str(entry.get("candidate_dir", ""))).resolve()
        if not source.is_dir():
            raise ValueError("candidate_dir missing")
        if any(p.is_symlink() for p in source.rglob("*")):
            raise ValueError("candidate tree may not contain symlinks")
        actual = digest_tree(str(source))
        if actual != expected:
            raise ValueError("candidate digest mismatch")

        cap_dir = self.slots / _safe_name(capability_id)
        cap_dir.mkdir(parents=True, exist_ok=True)
        dest = cap_dir / expected
        if dest.exists():
            if digest_tree(str(dest)) != expected:
                raise ValueError("existing staged slot digest mismatch")
            return {"capability_id": capability_id, "candidate_digest": expected, "slot": str(dest), "created": False}

        tmp = cap_dir / ("." + expected + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(source, tmp)
        if digest_tree(str(tmp)) != expected:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ValueError("staged snapshot digest mismatch")
        os.replace(tmp, dest)
        self.provenance.append("candidate_staged", capability_id=capability_id,
                               candidate_digest=expected, payload={"slot": str(dest)})
        return {"capability_id": capability_id, "candidate_digest": expected, "slot": str(dest), "created": True}

    def activate_from_registry(self, entry: Dict[str, Any], *, baseline_quality: Optional[float] = None,
                               baseline_latency_ms: Optional[float] = None) -> Dict[str, Any]:
        if baseline_quality is not None and not (0.0 <= float(baseline_quality) <= 1.0):
            raise ValueError("baseline_quality must be in 0..1")
        if baseline_latency_ms is not None and float(baseline_latency_ms) < 0:
            raise ValueError("baseline_latency_ms must be non-negative")
        staged = self.stage_from_registry(entry)
        capability_id = staged["capability_id"]
        digest = staged["candidate_digest"]
        data = self._load()
        active = data.setdefault("active", {})
        history = data.setdefault("history", {}).setdefault(capability_id, [])
        current = active.get(capability_id)
        if current and current.get("candidate_digest") == digest:
            return {"activated": False, "reason": "already_active", "entry": current}
        if current:
            history.append(current)

        evidence = entry.get("evidence") or {}
        latest = evidence.get("latest_evidence") or {}
        if baseline_quality is None:
            baseline_quality = ((latest.get("holdout") or {}).get("score"))
        new_entry = {
            "capability_id": capability_id,
            "candidate_digest": digest,
            "slot": staged["slot"],
            "activated_at": time.time(),
            "baseline_quality": baseline_quality,
            "baseline_latency_ms": baseline_latency_ms,
            "source": "verified_registry",
        }
        active[capability_id] = new_entry
        self._write(data)
        self.provenance.append("candidate_activated", capability_id=capability_id,
                               candidate_digest=digest, payload={"previous_digest": (current or {}).get("candidate_digest"),
                                                                 "baseline_quality": baseline_quality,
                                                                 "baseline_latency_ms": baseline_latency_ms})
        return {"activated": True, "entry": new_entry, "previous": current}

    def current(self, capability_id: str) -> Optional[Dict[str, Any]]:
        return self._load().get("active", {}).get(capability_id)

    def rollback(self, capability_id: str, *, reason: str, evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = self._load()
        active = data.setdefault("active", {})
        history = data.setdefault("history", {}).setdefault(capability_id, [])
        current = active.get(capability_id)
        if current is None:
            return {"rolled_back": False, "reason": "nothing_active"}
        if not history:
            return {"rolled_back": False, "reason": "no_previous_version", "current": current}
        previous = history[-1]
        previous_slot = Path(str(previous.get("slot", "")))
        previous_digest = str(previous.get("candidate_digest", ""))
        if not previous_slot.is_dir() or digest_tree(str(previous_slot)) != previous_digest:
            return {"rolled_back": False, "reason": "previous_slot_integrity_failed", "current": current}
        history.pop()
        active[capability_id] = previous
        self._write(data)
        self.provenance.append("automatic_rollback", capability_id=capability_id,
                               candidate_digest=str(current.get("candidate_digest", "")),
                               payload={"reason": reason, "restored_digest": previous.get("candidate_digest"),
                                        "evidence": evidence or {}})
        return {"rolled_back": True, "from": current, "to": previous, "reason": reason}
