from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .critic import PhotoLookQualityCritic
from .engine import PhotoLookEngine


class PhotoLookManager:
    def __init__(
        self,
        *,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        integrity_critics: Mapping[str, Sequence[object]],
    ):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.integrity_critics = {k: tuple(v) for k, v in integrity_critics.items()}
        self.engine = PhotoLookEngine(artifact_dir=self.artifact_dir)
        self.photo_critic = PhotoLookQualityCritic()

    def discover(self):
        return [self.engine.probe()]

    def status(self):
        return self.discover()

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        if request.media_type != "image":
            raise RuntimeError("photo-look manager supports image generation only")
        observers = self.observer_bindings.get("image", ())
        integrity = self.integrity_critics.get("image", ())
        if not observers:
            raise RuntimeError("no image observers configured")
        if not integrity:
            raise RuntimeError("no image integrity critic configured")

        lane = CandidateLane(self.engine.engine_id, self.engine, tuple(observers))
        result = AdaptiveFastPathController(
            [lane],
            tuple(integrity) + (self.photo_critic,),
            initial_width=1,
            repair_width=1,
        ).run(request)

        # Keep rejected photo candidates visible for visual inspection while
        # preserving the fail-closed rejected status.
        if result.best_candidate is None:
            observed = [
                candidate
                for round_ in result.rounds
                for candidate in round_.candidates
            ]
            if observed:
                inspected = max(
                    observed,
                    key=lambda x: (float(x.critique.score), x.backend_id),
                )
                result = replace(result, best_candidate=inspected)

        return MediaSkillRun(
            result,
            (f"media.generate.image:{self.engine.engine_id}",),
        )
