from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


class QuarantineRepairEmitter:
    """Emit non-executable repair requests into the Skill Factory inbox."""

    def __init__(self, inbox_dir: str):
        self.inbox = Path(inbox_dir); self.inbox.mkdir(parents=True, exist_ok=True)

    def emit(self, *, capability_id: str, candidate_digest: str, reason: str,
             family: str = "", evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
        spec = {
            "capability_id": str(capability_id),
            "request_type": "quarantine_repair",
            "repair_of_candidate_digest": str(candidate_digest),
            "family": str(family or ""),
            "failure_reason": str(reason),
            "requirements": {
                "new_candidate_bytes": True,
                "new_untouched_holdout_evidence_required_for_release": True,
                "must_pass_static_safety": True,
                "must_pass_sandbox": True,
                "must_not_weaken_tests": True,
                "must_not_hardcode_benchmark_answers": True,
            },
            "evidence_summary": evidence or {},
            "metadata": {"kind": "skill_factory_repair_request", "executable": False},
        }
        canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        cap = "".join(c if c.isalnum() or c in "._-" else "_" for c in str(capability_id)) or "unknown"
        final = self.inbox / f"repair__{cap}__{str(candidate_digest)[:12]}__{digest[:16]}.json"
        if final.exists():
            return {"queued": False, "duplicate": True, "path": str(final), "sha256": digest, "spec": spec}
        fd, tmp = tempfile.mkstemp(prefix=".tmp-repair-", suffix=".json", dir=str(self.inbox))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(canonical); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, final)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return {"queued": True, "duplicate": False, "path": str(final), "sha256": digest, "spec": spec}
