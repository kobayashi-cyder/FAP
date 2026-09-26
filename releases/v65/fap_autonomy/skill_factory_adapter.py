from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class SkillFactoryOutputAdapter:
    """Validates a non-executable Skill Factory candidate manifest.

    The adapter deliberately accepts only Python argv commands using the {python}
    token. It does not run a shell and requires evaluator-owned holdout files to
    live outside the candidate source tree.
    """

    def __init__(self, *, candidate_root: str, evaluator_root: str):
        self.candidate_root = Path(candidate_root).resolve()
        self.evaluator_root = Path(evaluator_root).resolve()

    @staticmethod
    def _command(value: Any, *, role: str, cwd: Path) -> List[str]:
        if not isinstance(value, list) or not value or not all(isinstance(x, str) and x for x in value):
            raise ValueError("command must be a non-empty argv list")
        if value[0] != "{python}":
            raise ValueError("only {python} commands are accepted")
        args = list(value[1:])
        if not args:
            raise ValueError("python command requires arguments")
        if args[0] == "-c":
            raise ValueError("python -c is not accepted")
        if args[0] == "-m":
            if role != "unit" or len(args) < 2 or args[1] != "unittest":
                raise ValueError("only -m unittest is accepted for module execution")
        else:
            script = (cwd / args[0]).resolve()
            if not _inside(script, cwd) or script.suffix.lower() != ".py" or not script.is_file():
                raise ValueError("python script must be an existing .py file inside its evaluator root")
        return [sys.executable, *args]

    def load(self, path: str) -> Dict[str, Any]:
        manifest_path = Path(path).resolve()
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if raw.get("schema") != 1:
            raise ValueError("unsupported candidate manifest schema")
        capability_id = str(raw.get("capability_id", "")).strip()
        request_id = str(raw.get("request_id", "")).strip()
        if not capability_id or not request_id:
            raise ValueError("request_id and capability_id are required")

        candidate_dir = (self.candidate_root / str(raw.get("candidate_relpath", ""))).resolve()
        evaluator_cwd = (self.evaluator_root / str(raw.get("evaluator_relpath", "."))).resolve()
        if not _inside(candidate_dir, self.candidate_root) or not candidate_dir.is_dir():
            raise ValueError("candidate path escapes candidate_root or does not exist")
        if not _inside(evaluator_cwd, self.evaluator_root) or not evaluator_cwd.is_dir():
            raise ValueError("evaluator path escapes evaluator_root or does not exist")

        unit_command = self._command(raw.get("unit_command"), role="unit", cwd=candidate_dir)
        dev_command = self._command(raw.get("dev_command"), role="dev", cwd=evaluator_cwd)
        trials = raw.get("trials")
        if not isinstance(trials, list) or not trials:
            raise ValueError("at least one trial is required")
        normalized_trials = []
        seen = set()
        for item in trials:
            trial_id = str(item.get("trial_id", "")).strip()
            if not trial_id or trial_id in seen:
                raise ValueError("trial_id must be unique and non-empty")
            seen.add(trial_id)
            holdout_paths = []
            for rel in item.get("holdout_paths") or []:
                p = (self.evaluator_root / str(rel)).resolve()
                if not _inside(p, self.evaluator_root) or not p.is_file():
                    raise ValueError("holdout path escapes evaluator_root or does not exist")
                if _inside(p, candidate_dir):
                    raise ValueError("holdout must be evaluator-owned and outside candidate_dir")
                holdout_paths.append(str(p))
            if not holdout_paths:
                raise ValueError("holdout_paths required")
            normalized_trials.append({
                "trial_id": trial_id,
                "holdout_paths": holdout_paths,
                "holdout_command": self._command(item.get("holdout_command"), role="holdout", cwd=evaluator_cwd),
            })

        return {
            "schema": 1,
            "request_id": request_id,
            "capability_id": capability_id,
            "candidate_dir": str(candidate_dir),
            "evaluator_cwd": str(evaluator_cwd),
            "unit_command": unit_command,
            "dev_command": dev_command,
            "trials": normalized_trials,
            "ram_mb": raw.get("ram_mb"),
            "production_baseline_latency_ms": raw.get("production_baseline_latency_ms"),
            "metadata": raw.get("metadata") or {},
        }

    @staticmethod
    def artifact_for_trial(candidate: Dict[str, Any], trial: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "candidate_dir": candidate["candidate_dir"],
            "evaluator_cwd": candidate["evaluator_cwd"],
            "unit_command": candidate["unit_command"],
            "dev_command": candidate["dev_command"],
            "holdout_command": trial["holdout_command"],
            "holdout_paths": trial["holdout_paths"],
            "ram_mb": candidate.get("ram_mb"),
        }
