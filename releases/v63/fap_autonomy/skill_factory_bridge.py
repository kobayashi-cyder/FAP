from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable

from .promotion_ledger import digest_tree


class SkillFactoryOutputError(ValueError):
    pass


class SkillFactoryOutputAdapter:
    """Validate a Skill Factory output manifest without importing candidate code."""

    REQUIRED = {"capability_id", "candidate_dir", "unit_command", "dev_command", "holdout_command", "holdout_paths"}

    def load(self, manifest_path: str) -> Dict[str, Any]:
        p = Path(manifest_path).resolve()
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise SkillFactoryOutputError("manifest must be an object")
        missing = sorted(self.REQUIRED - set(obj))
        if missing:
            raise SkillFactoryOutputError("missing fields: " + ", ".join(missing))
        candidate = Path(obj["candidate_dir"]).resolve()
        if not candidate.is_dir():
            raise SkillFactoryOutputError("candidate_dir does not exist")
        holdouts = [Path(x).resolve() for x in obj.get("holdout_paths") or []]
        if not holdouts or any(not x.is_file() for x in holdouts):
            raise SkillFactoryOutputError("holdout_paths must be existing files")
        for key in ("unit_command", "dev_command", "holdout_command"):
            cmd = obj.get(key)
            if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd):
                raise SkillFactoryOutputError(f"{key} must be a non-empty string list")
        normalized = dict(obj)
        normalized["candidate_dir"] = str(candidate)
        normalized["holdout_paths"] = [str(x) for x in holdouts]
        normalized["evaluator_cwd"] = str(Path(obj.get("evaluator_cwd", candidate)).resolve())
        normalized["candidate_digest"] = digest_tree(str(candidate))
        return normalized


class SkillFactoryCommandBridge:
    """Invoke an already-trusted Skill Factory process, then validate its manifest."""

    def __init__(self, command_prefix: Iterable[str], *, timeout_seconds: float = 60.0):
        self.command_prefix = [str(x) for x in command_prefix]
        if not self.command_prefix:
            raise ValueError("command_prefix required")
        self.timeout_seconds = float(timeout_seconds)
        self.adapter = SkillFactoryOutputAdapter()

    def generate(self, request_path: str, *, output_dir: str) -> Dict[str, Any]:
        out = Path(output_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
        manifest = out / "candidate_artifact.json"
        env = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
               "WINDIR": os.environ.get("WINDIR", ""), "PYTHONIOENCODING": "utf-8"}
        cmd = self.command_prefix + [str(Path(request_path).resolve()), str(manifest)]
        t0 = time.perf_counter()
        cp = subprocess.run(cmd, cwd=str(out), env=env, capture_output=True, text=True, timeout=self.timeout_seconds)
        elapsed = time.perf_counter() - t0
        if cp.returncode != 0:
            raise RuntimeError(f"skill factory failed rc={cp.returncode}: {cp.stderr[-2000:]}")
        if not manifest.exists():
            raise RuntimeError("skill factory did not produce candidate_artifact.json")
        artifact = self.adapter.load(str(manifest))
        artifact["factory_seconds"] = elapsed
        artifact["factory_stdout_tail"] = cp.stdout[-2000:]
        return artifact
