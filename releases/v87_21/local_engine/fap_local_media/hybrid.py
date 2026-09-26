from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import HTTPMediaEngine, MediaSkillRun, MediaSkillRegistry
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .a1111 import A1111Discovery


@dataclass
class LocalSkillRecord:
    engine_id: str
    base_url: str
    stage: str = "candidate"
    verified_successes: int = 0
    verified_failures: int = 0
    distinct_digests: tuple[str, ...] = ()
    score_ema: float = 0.0

    @property
    def skill_id(self):
        return f"media.generate.image:{self.engine_id}"


class LocalSkillStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records: dict[str, LocalSkillRecord] = {}
        if self.path.is_file():
            self._load()

    def ensure(self, engine_id: str, base_url: str) -> LocalSkillRecord:
        skill_id = f"media.generate.image:{engine_id}"
        record = self.records.get(skill_id)
        if record is None:
            record = LocalSkillRecord(engine_id, base_url)
            self.records[skill_id] = record
            self._save()
        return record

    def record(self, skill_id: str, *, digest: str, score: float, passed: bool):
        record = self.records[skill_id]
        total = record.verified_successes + record.verified_failures
        score = max(0.0, min(1.0, float(score)))
        record.score_ema = score if total == 0 else 0.35 * score + 0.65 * record.score_ema
        if passed and digest and digest not in record.distinct_digests:
            record.verified_successes += 1
            record.distinct_digests = tuple((*record.distinct_digests, digest)[-32:])
            if record.stage == "candidate":
                record.stage = "testing"
            elif record.stage == "testing" and record.verified_successes >= 2:
                record.stage = "shadow"
            elif record.stage == "shadow" and record.verified_successes >= 3 and record.score_ema >= 0.85:
                record.stage = "active"
        elif not passed:
            record.verified_failures += 1
            if record.verified_failures >= 3 and record.verified_successes == 0:
                record.stage = "rejected"
        self._save()
        return record

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "fap.local-media-skills.v1",
            "records": [
                {
                    "skill_id": skill_id,
                    "engine_id": r.engine_id,
                    "base_url": r.base_url,
                    "stage": r.stage,
                    "verified_successes": r.verified_successes,
                    "verified_failures": r.verified_failures,
                    "distinct_digests": list(r.distinct_digests),
                    "score_ema": r.score_ema,
                }
                for skill_id, r in sorted(self.records.items())
            ],
        }
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _load(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema") != "fap.local-media-skills.v1":
            raise ValueError("unsupported local media skill registry schema")
        for raw in payload.get("records", []):
            record = LocalSkillRecord(
                engine_id=str(raw["engine_id"]),
                base_url=str(raw["base_url"]),
                stage=str(raw["stage"]),
                verified_successes=int(raw["verified_successes"]),
                verified_failures=int(raw["verified_failures"]),
                distinct_digests=tuple(str(x) for x in raw["distinct_digests"]),
                score_ema=float(raw["score_ema"]),
            )
            if raw["skill_id"] != record.skill_id:
                raise ValueError("local media skill identity mismatch")
            self.records[record.skill_id] = record


class HybridAutonomousMediaSkillManager:
    """Use loopback A1111/Forge engines and V87.19 remote engines in one FAP route."""

    def __init__(
        self,
        registry: MediaSkillRegistry,
        *,
        local_store: LocalSkillStateStore,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        critics: Mapping[str, Sequence[object]],
        remote_transports=None,
        local_transport=None,
        local_candidates=None,
        sleep_fn=None,
    ):
        self.registry = registry
        self.local_store = local_store
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.critics = {k: tuple(v) for k, v in critics.items()}
        self.remote_transports = dict(remote_transports or {})
        self.sleep_fn = sleep_fn
        self.discovery = A1111Discovery(
            artifact_dir=self.artifact_dir,
            transport=local_transport,
            candidates=local_candidates,
        )
        self._local = {}

    def discover(self):
        remote = []
        try:
            remote = MediaSkillRegistry.discover_from_environment(self.registry)
        except Exception:
            remote = []
        local = self.discovery.discover()
        self._local = {}
        for engine, probe in local:
            self._local[engine.engine_id] = (engine, probe)
            self.local_store.ensure(engine.engine_id, engine.base_url)
        return {"remote": remote, "local": local}

    def skill_status(self):
        self.discover()
        rows = []
        for engine_id, (_, probe) in sorted(self._local.items()):
            record = self.local_store.ensure(engine_id, probe.base_url)
            rows.append({
                "skill_id": record.skill_id,
                "engine_id": record.engine_id,
                "media_type": "image",
                "stage": record.stage,
                "score_ema": round(record.score_ema, 4),
                "verified_successes": record.verified_successes,
                "verified_failures": record.verified_failures,
                "credential_present": True,
                "endpoint_origin": probe.base_url,
                "adapter": "a1111-local",
                "model_count": probe.model_count,
                "model_titles": list(probe.model_titles[:8]),
            })
        for skill_id, record in sorted(self.registry.records.items()):
            rows.append({
                "skill_id": skill_id,
                "engine_id": record.engine.engine_id,
                "media_type": record.engine.media_type,
                "stage": record.stage,
                "score_ema": round(record.score_ema, 4),
                "verified_successes": record.verified_successes,
                "verified_failures": record.verified_failures,
                "credential_present": bool(os.environ.get(record.engine.token_env)),
                "endpoint_origin": record.engine.endpoint,
                "adapter": "v87.19-https",
            })
        return rows

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        self.discover()
        observers = self.observer_bindings.get(request.media_type, ())
        critics = self.critics.get(request.media_type, ())
        if not observers:
            raise RuntimeError(f"no {request.media_type} observers configured")
        if not critics:
            raise RuntimeError(f"no {request.media_type} critics configured")

        lanes = []
        local_ids = set()
        if request.media_type == "image":
            local_rows = []
            for engine_id, (engine, _) in self._local.items():
                record = self.local_store.ensure(engine_id, engine.base_url)
                if record.stage != "rejected":
                    local_rows.append((record, engine))
            local_rows.sort(
                key=lambda pair: (
                    {"active": 0, "shadow": 1, "testing": 2, "candidate": 3}.get(pair[0].stage, 9),
                    -pair[0].score_ema,
                    pair[0].engine_id,
                )
            )
            for record, engine in local_rows:
                lanes.append(CandidateLane(record.engine_id, engine, tuple(observers)))
                local_ids.add(record.engine_id)

        for record in self.registry.eligible(request.media_type):
            if not os.environ.get(record.engine.token_env):
                continue
            kwargs = {}
            if record.engine.engine_id in self.remote_transports:
                kwargs["transport"] = self.remote_transports[record.engine.engine_id]
            if self.sleep_fn is not None:
                kwargs["sleep_fn"] = self.sleep_fn
            lanes.append(
                CandidateLane(
                    record.engine.engine_id,
                    HTTPMediaEngine(
                        record.engine,
                        artifact_dir=self.artifact_dir,
                        **kwargs,
                    ),
                    tuple(observers),
                )
            )

        if not lanes:
            raise RuntimeError(f"no {request.media_type} generation engines discovered")

        result = AdaptiveFastPathController(
            lanes,
            critics,
            initial_width=1,
            repair_width=1,
        ).run(request)

        updated = set()
        for round_ in result.rounds:
            for candidate in round_.candidates:
                passed = (
                    not candidate.critique.has_fatal
                    and candidate.critique.score >= request.min_score
                )
                if candidate.backend_id in local_ids:
                    record = self.local_store.ensure(
                        candidate.backend_id,
                        self._local[candidate.backend_id][0].base_url,
                    )
                    self.local_store.record(
                        record.skill_id,
                        digest=candidate.artifact.digest,
                        score=candidate.critique.score,
                        passed=passed,
                    )
                    updated.add(record.skill_id)
                else:
                    skill_id = f"media.generate.{request.media_type}:{candidate.backend_id}"
                    if skill_id in self.registry.records:
                        self.registry.record_outcome(
                            skill_id,
                            digest=candidate.artifact.digest,
                            score=candidate.critique.score,
                            passed=passed,
                            independent=True,
                            reason="quality_gate_satisfied" if passed else "quality_gate_not_satisfied",
                        )
                        updated.add(skill_id)

        return MediaSkillRun(result, tuple(sorted(updated)))
