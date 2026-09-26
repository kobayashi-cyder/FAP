from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .holdout_seal import HoldoutSeal
from .models import ImprovementBudget
from .promotion_ledger import PromotionLedger, digest_tree
from .verifier import StaticSafetyGate


class CommandRunner:
    """Subprocess wrapper with timeout and best-effort peak RSS measurement.

    Production should still replace process isolation with the existing FAP OS/container sandbox.
    """

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = float(timeout_seconds)

    def run(self, command: List[str], *, cwd: str, extra_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        import tempfile
        env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
        }
        if extra_env:
            env.update({str(k): str(v) for k, v in extra_env.items()})
        t0 = time.perf_counter()
        peak_rss = None
        try:
            import psutil  # optional measurement dependency; execution still works without it
        except Exception:
            psutil = None
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as out, tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
            proc = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err, text=True, env=env)
            root_ps = psutil.Process(proc.pid) if psutil else None
            timed_out = False
            while proc.poll() is None:
                elapsed = time.perf_counter() - t0
                if elapsed > self.timeout_seconds:
                    timed_out = True
                    if root_ps:
                        try:
                            for child in root_ps.children(recursive=True):
                                child.kill()
                        except Exception:
                            pass
                    proc.kill()
                    break
                if root_ps:
                    try:
                        procs = [root_ps] + root_ps.children(recursive=True)
                        rss = sum(x.memory_info().rss for x in procs if x.is_running()) / (1024.0 * 1024.0)
                        peak_rss = max(float(peak_rss or 0.0), rss)
                    except Exception:
                        pass
                time.sleep(0.02)
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
            if root_ps and peak_rss is None:
                try:
                    peak_rss = root_ps.memory_info().rss / (1024.0 * 1024.0)
                except Exception:
                    pass
            out.seek(0); err.seek(0)
            stdout = out.read()[-16000:]
            stderr = err.read()[-16000:]
            elapsed = time.perf_counter() - t0
            return {
                "pass": (not timed_out) and proc.returncode == 0,
                "returncode": None if timed_out else proc.returncode,
                "stdout": stdout,
                "stderr": "timeout" if timed_out else stderr,
                "seconds": elapsed,
                "peak_rss_mb": peak_rss,
            }


def _parse_score(run: Dict[str, Any]) -> Dict[str, Any]:
    if not run.get("pass"):
        return {"valid": False, "score": 0.0, "cases": 0, "passed": 0, "error": "command_failed"}
    lines = [x.strip() for x in str(run.get("stdout", "")).splitlines() if x.strip()]
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "score" in obj:
            score = float(obj["score"])
            cases = int(obj.get("cases", 0))
            passed = int(obj.get("passed", round(score * cases) if cases else 0))
            if 0.0 <= score <= 1.0 and cases >= 0 and 0 <= passed <= cases:
                return {"valid": True, "score": score, "cases": cases, "passed": passed, "raw": obj}
    return {"valid": False, "score": 0.0, "cases": 0, "passed": 0, "error": "missing_json_score"}


class CandidatePromotionPipeline:
    """V62 closed-loop candidate evaluator.

    Contract:
      artifact = {
        candidate_dir, unit_command, dev_command, holdout_command,
        evaluator_cwd, holdout_paths, ram_mb
      }

    Benchmark commands must print a JSON object containing score on their final output.
    Holdout files are evaluator-owned and hash sealed before/after execution.
    """

    def __init__(self, *, ledger: PromotionLedger, registry=None,
                 budget: Optional[ImprovementBudget] = None):
        self.ledger = ledger
        self.registry = registry
        self.budget = budget or ImprovementBudget()
        self.gate = StaticSafetyGate()
        self.runner = CommandRunner(self.budget.max_test_seconds)

    def evaluate_once(self, *, capability_id: str, artifact: Dict[str, Any], trial_id: str,
                      baseline_dev_score: float, min_dev_gain: float = 0.0,
                      min_holdout_score: float = 0.5) -> Dict[str, Any]:
        candidate_dir = str(Path(artifact["candidate_dir"]).resolve())
        evaluator_cwd = str(Path(artifact.get("evaluator_cwd", candidate_dir)).resolve())
        digest = digest_tree(candidate_dir)
        static = self.gate.inspect_tree(candidate_dir)
        if not static["safe"]:
            return self._terminal("static_reject", capability_id, digest, trial_id, static=static)

        holdout_paths = artifact.get("holdout_paths") or []
        if not holdout_paths:
            return self._terminal("holdout_unsealed", capability_id, digest, trial_id, static=static)
        seal = HoldoutSeal(holdout_paths)

        unit = self.runner.run(list(artifact["unit_command"]), cwd=candidate_dir)
        if not unit["pass"]:
            return self._terminal("unit_reject", capability_id, digest, trial_id, static=static, unit=unit)

        dev_run = self.runner.run(list(artifact["dev_command"]), cwd=evaluator_cwd)
        dev = _parse_score(dev_run)
        if not dev["valid"]:
            return self._terminal("dev_benchmark_invalid", capability_id, digest, trial_id, static=static, unit=unit, dev=dev, dev_run=dev_run)

        hold_run = self.runner.run(list(artifact["holdout_command"]), cwd=evaluator_cwd)
        holdout = _parse_score(hold_run)
        seal_result = seal.verify()
        if not seal_result["intact"]:
            return self._terminal("holdout_tampered", capability_id, digest, trial_id, static=static, unit=unit, dev=dev, holdout=holdout, seal=seal_result)
        if not holdout["valid"]:
            return self._terminal("holdout_benchmark_invalid", capability_id, digest, trial_id, static=static, unit=unit, dev=dev, holdout=holdout, seal=seal_result)

        code_bytes = sum(p.stat().st_size for p in Path(candidate_dir).rglob("*.py") if p.is_file())
        disk_bytes = sum(p.stat().st_size for p in Path(candidate_dir).rglob("*") if p.is_file())
        measured_rss = [x.get("peak_rss_mb") for x in (unit, dev_run, hold_run) if x.get("peak_rss_mb") is not None]
        ram_mb = max(measured_rss) if measured_rss else artifact.get("ram_mb")
        ram_source = "measured_peak_rss" if measured_rss else ("artifact_supplied" if ram_mb is not None else "missing")
        total_seconds = unit["seconds"] + dev_run["seconds"] + hold_run["seconds"]
        resource_ok = (
            ram_mb is not None
            and code_bytes / 1024.0 <= self.budget.max_generated_code_kb
            and float(ram_mb) <= self.budget.max_ram_mb
            and disk_bytes / (1024.0 * 1024.0) <= self.budget.max_disk_mb
            and total_seconds <= self.budget.max_test_seconds
        )
        regression_delta = float(dev["score"]) - float(baseline_dev_score)
        dev_ok = dev["score"] >= baseline_dev_score + min_dev_gain
        holdout_ok = holdout["score"] >= min_holdout_score and holdout["score"] >= dev["score"] * 0.85
        success = bool(dev_ok and holdout_ok and resource_ok and regression_delta >= -self.budget.max_regression)
        confidence = min(0.98, 0.65 + 0.18 * holdout["score"] + 0.12 * dev["score"]) if success else 0.25
        evidence = {
            "static": static,
            "unit": {"pass": unit["pass"], "seconds": unit["seconds"]},
            "dev": dev,
            "holdout": holdout,
            "seal": {"intact": seal_result["intact"], "hash": seal_result["hash"]},
            "resources": {
                "code_kb": code_bytes / 1024.0,
                "disk_mb": disk_bytes / (1024.0 * 1024.0),
                "ram_mb": ram_mb,
                "ram_source": ram_source,
                "seconds": total_seconds,
            },
            "criteria": {
                "baseline_dev_score": baseline_dev_score,
                "min_dev_gain": min_dev_gain,
                "min_holdout_score": min_holdout_score,
                "dev_ok": dev_ok,
                "holdout_ok": holdout_ok,
                "resource_ok": resource_ok,
            },
        }
        evidence_key_payload = {
            "candidate_digest": digest,
            "holdout_hash": seal_result["hash"],
            "dev_command": list(artifact["dev_command"]),
            "holdout_command": list(artifact["holdout_command"]),
            "baseline_dev_score": float(baseline_dev_score),
            "min_dev_gain": float(min_dev_gain),
            "min_holdout_score": float(min_holdout_score),
        }
        evidence_key = hashlib.sha256(json.dumps(evidence_key_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        evidence["evidence_key"] = evidence_key
        inserted = self.ledger.record_trial(
            trial_id=trial_id, capability_id=capability_id, candidate_digest=digest,
            success=success, confidence=confidence, dev_score=dev["score"],
            holdout_score=holdout["score"], regression_delta=regression_delta,
            resource_ok=resource_ok, holdout_hash=seal_result["hash"], evidence_key=evidence_key, evidence=evidence,
        )
        state = self.ledger.state(capability_id, digest, max_regression=self.budget.max_regression)
        registered = False
        if inserted and state.state == "consolidated" and self.registry is not None:
            registered = bool(self.registry.register_verified(
                capability_id, artifact,
                {"candidate_digest": digest, "lifecycle": asdict(state), "latest_evidence": evidence},
            ))
        return {
            "status": "candidate_evaluated" if inserted else "duplicate_trial_or_evidence_ignored",
            "trial_id": trial_id,
            "capability_id": capability_id,
            "candidate_digest": digest,
            "success": success,
            "evidence": evidence,
            "lifecycle": asdict(state),
            "registered": registered,
        }

    @staticmethod
    def _terminal(status: str, capability_id: str, digest: str, trial_id: str, **extra):
        return {"status": status, "capability_id": capability_id, "candidate_digest": digest, "trial_id": trial_id, **extra}
