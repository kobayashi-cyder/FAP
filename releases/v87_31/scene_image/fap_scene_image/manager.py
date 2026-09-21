from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .critic import SceneQualityCritic
from .engine import SceneImageEngine


class SceneImageManager:
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
        self.engine = SceneImageEngine(artifact_dir=self.artifact_dir)
        self.scene_critic = SceneQualityCritic()

    def discover(self):
        return [self.engine.probe()]

    def status(self):
        return self.discover()

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        if request.media_type != "image":
            raise RuntimeError("scene image manager supports image generation only")
        observers = self.observer_bindings.get("image", ())
        if not observers:
            raise RuntimeError("no image observers configured")
        integrity = self.integrity_critics.get("image", ())
        if not integrity:
            raise RuntimeError("no image integrity critic configured")

        lane = CandidateLane(self.engine.engine_id, self.engine, tuple(observers))
        critics = tuple(integrity) + (self.scene_critic,)
        result = AdaptiveFastPathController(
            [lane],
            critics,
            initial_width=1,
            repair_width=1,
        ).run(request)
        return MediaSkillRun(
            result,
            (f"media.generate.image:{self.engine.engine_id}",),
        )
