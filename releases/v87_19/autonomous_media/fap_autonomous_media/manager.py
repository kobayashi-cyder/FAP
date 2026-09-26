from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .engine import HTTPMediaEngine, Transport
from .registry import MediaSkillRegistry


@dataclass(frozen=True)
class MediaSkillRun:
    result: object
    updated_skills: tuple[str, ...]


class AutonomousMediaSkillManager:
    """Discover -> execute -> independently verify -> promote media generation skills."""

    def __init__(
        self,
        registry: MediaSkillRegistry,
        *,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        critics: Mapping[str, Sequence[object]],
        transports: Mapping[str, Transport] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.registry = registry
        self.artifact_dir = Path(artifact_dir)
        self.observer_bindings = {
            key: tuple(value) for key, value in observer_bindings.items()
        }
        self.critics = {key: tuple(value) for key, value in critics.items()}
        self.transports = dict(transports or {})
        self.sleep_fn = sleep_fn

    def discover(self, variable: str = "FAP_MEDIA_ENGINES_JSON"):
        return MediaSkillRegistry.discover_from_environment(
            self.registry,
            variable=variable,
        )

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        records = self.registry.eligible(request.media_type)
        if not records:
            self.discover()
            records = self.registry.eligible(request.media_type)
        if not records:
            raise RuntimeError(f"no {request.media_type} generation engines discovered")

        observers = self.observer_bindings.get(request.media_type, ())
        critics = self.critics.get(request.media_type, ())
        if not observers:
            raise RuntimeError(f"no {request.media_type} observers configured")
        if not critics:
            raise RuntimeError(f"no {request.media_type} critics configured")

        lanes = []
        by_backend = {}
        for record in records:
            kwargs = {}
            if record.engine.engine_id in self.transports:
                kwargs["transport"] = self.transports[record.engine.engine_id]
            if self.sleep_fn is not None:
                kwargs["sleep_fn"] = self.sleep_fn
            engine = HTTPMediaEngine(
                record.engine,
                artifact_dir=self.artifact_dir,
                **kwargs,
            )
            lane = CandidateLane(
                record.engine.engine_id,
                engine,
                tuple(observers),
            )
            lanes.append(lane)
            by_backend[record.engine.engine_id] = record

        controller = AdaptiveFastPathController(
            lanes,
            critics,
            initial_width=1,
            repair_width=1,
        )
        result = controller.run(request)

        updated = set()
        for round_ in result.rounds:
            for candidate in round_.candidates:
                record = by_backend[candidate.backend_id]
                passed = (
                    not candidate.critique.has_fatal
                    and candidate.critique.score >= request.min_score
                )
                self.registry.record_outcome(
                    record.skill_id,
                    digest=candidate.artifact.digest,
                    score=candidate.critique.score,
                    passed=passed,
                    independent=True,
                    reason=(
                        "quality_gate_satisfied"
                        if passed
                        else "quality_gate_not_satisfied"
                    ),
                )
                updated.add(record.skill_id)

        return MediaSkillRun(result, tuple(sorted(updated)))
