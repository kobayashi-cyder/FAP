from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Mapping

from fap_autonomous_media import AutonomousMediaSkillManager, MediaSkillRegistry
from fap_media_generation import Critique, CritiqueIssue, GenerationRequest
from fap_observed_media import ObservationEnvelope, ObserverBinding


class ActualFileObserver:
    """Read back the generated file instead of trusting generator metadata."""

    def observe(self, request, artifact):
        path = Path(artifact.locator)
        data = path.read_bytes()
        return ObservationEnvelope(
            artifact.digest,
            {
                "exists": path.is_file(),
                "bytes": len(data),
                "sha256": sha256(data).hexdigest(),
                "suffix": path.suffix.lower(),
            },
            observer_id="fap.media-lab.actual-file.v1",
            evidence_kind="actual-file",
        )


class ArtifactIntegrityCritic:
    """Operational verifier for the Media Lab.

    This verifies that real bytes were written and digest-bound. It is deliberately
    not presented as a semantic/aesthetic image or video quality score.
    """

    def critique(self, request, artifact):
        evidence = artifact.metadata.get("actual_file_evidence")
        if not isinstance(evidence, dict):
            return Critique(
                0.0,
                (
                    CritiqueIssue(
                        "actual_file_missing",
                        "actual generated file evidence is missing",
                        "fatal",
                    ),
                ),
                evidence={"kind": "artifact-integrity"},
            )
        expected = artifact.digest
        actual = str(evidence.get("sha256", ""))
        byte_count = int(evidence.get("bytes", 0) or 0)
        if byte_count <= 0 or actual != expected:
            return Critique(
                0.0,
                (
                    CritiqueIssue(
                        "artifact_integrity",
                        "generated file bytes do not match artifact digest",
                        "fatal",
                    ),
                ),
                evidence={
                    "kind": "artifact-integrity",
                    "bytes": byte_count,
                    "digest_match": actual == expected,
                },
            )
        return Critique(
            1.0,
            (),
            evidence={
                "kind": "artifact-integrity",
                "bytes": byte_count,
                "digest_match": True,
            },
        )


class MediaLabRuntime:
    def __init__(
        self,
        *,
        runtime_dir: str | Path,
        registry: MediaSkillRegistry | None = None,
        manager: AutonomousMediaSkillManager | None = None,
        transports: Mapping | None = None,
        sleep_fn=None,
    ):
        self.runtime_dir = Path(runtime_dir)
        self.artifact_dir = self.runtime_dir / "artifacts"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry or MediaSkillRegistry(self.runtime_dir / "media_skills.json")

        observer = ActualFileObserver()
        critic = ArtifactIntegrityCritic()
        self.manager = manager or AutonomousMediaSkillManager(
            self.registry,
            artifact_dir=self.artifact_dir,
            observer_bindings={
                "image": (
                    ObserverBinding(
                        "actual_file_evidence",
                        observer,
                        ("image",),
                    ),
                ),
                "video": (
                    ObserverBinding(
                        "actual_file_evidence",
                        observer,
                        ("video",),
                    ),
                ),
            },
            critics={
                "image": (critic,),
                "video": (critic,),
            },
            transports=transports,
            sleep_fn=sleep_fn,
        )

    def discover(self):
        return self.manager.discover()

    def status(self) -> dict:
        try:
            self.discover()
            discovery_error = ""
        except Exception as exc:
            discovery_error = f"{type(exc).__name__}: {exc}"

        skills = []
        for skill_id, record in sorted(self.registry.records.items()):
            credential_present = bool(__import__("os").environ.get(record.engine.token_env))
            skills.append(
                {
                    "skill_id": skill_id,
                    "engine_id": record.engine.engine_id,
                    "media_type": record.engine.media_type,
                    "stage": record.stage,
                    "score_ema": round(float(record.score_ema), 4),
                    "verified_successes": record.verified_successes,
                    "verified_failures": record.verified_failures,
                    "credential_present": credential_present,
                    "endpoint_origin": _origin(record.engine.endpoint),
                }
            )
        return {
            "name": "FAP MEDIA LAB",
            "version": "87.20",
            "state": "ready" if skills and any(x["credential_present"] for x in skills) else "needs_engine",
            "skills": skills,
            "discovery_error": discovery_error,
            "artifact_dir": str(self.artifact_dir),
            "verification": {
                "current": "artifact-integrity",
                "semantic_quality": False,
                "note": "The built-in Media Lab verifier proves real artifact bytes and digest identity; it does not claim semantic/aesthetic quality.",
            },
        }

    def generate(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        prompt = str(payload.get("prompt", "")).strip()
        media_type = str(payload.get("media_type", "image")).strip().lower()
        if not prompt:
            raise ValueError("prompt is required")
        if media_type not in {"image", "video"}:
            raise ValueError("media_type must be image or video")

        width = int(payload.get("width", 1024))
        height = int(payload.get("height", 1024))
        max_attempts = int(payload.get("max_attempts", 3))
        constraints_raw = payload.get("constraints", ())
        if isinstance(constraints_raw, str):
            constraints = tuple(
                x.strip() for x in constraints_raw.split("\n") if x.strip()
            )
        elif isinstance(constraints_raw, (list, tuple)):
            constraints = tuple(str(x).strip() for x in constraints_raw if str(x).strip())
        else:
            raise ValueError("constraints must be text or list")

        kwargs = {
            "prompt": prompt,
            "media_type": media_type,
            "width": width,
            "height": height,
            "max_attempts": max_attempts,
            "min_score": 0.99,
            "constraints": constraints,
        }
        if media_type == "video":
            kwargs["duration_s"] = float(payload.get("duration_s", 4.0))
            kwargs["fps"] = int(payload.get("fps", 24))

        request = GenerationRequest(**kwargs)
        run = self.manager.generate(request)
        result = run.result
        candidate = result.best_candidate
        response = {
            "accepted": bool(result.accepted),
            "status": result.status,
            "stop_reason": result.stop_reason,
            "generator_calls": result.generator_calls,
            "rounds": len(result.rounds),
            "updated_skills": list(run.updated_skills),
            "artifact": None,
        }
        if candidate is not None:
            artifact = candidate.artifact
            path = Path(artifact.locator)
            response["artifact"] = {
                "media_type": artifact.media_type,
                "mime_type": artifact.mime_type,
                "digest": artifact.digest,
                "filename": path.name,
                "url": "/artifacts/" + path.name,
                "backend_id": candidate.backend_id,
                "verification_score": float(candidate.critique.score),
                "verification_kind": "artifact-integrity",
                "issues": [
                    {
                        "code": issue.code,
                        "severity": issue.severity,
                        "detail": issue.detail,
                    }
                    for issue in candidate.critique.issues
                ],
            }
        return response

    def artifact_path(self, filename: str) -> Path:
        name = Path(filename).name
        if name != filename or not name:
            raise FileNotFoundError("invalid artifact name")
        path = self.artifact_dir / name
        if not path.is_file():
            raise FileNotFoundError(name)
        return path


def _origin(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
