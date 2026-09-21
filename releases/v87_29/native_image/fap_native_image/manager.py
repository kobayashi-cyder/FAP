from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .engine import NativeImageEngine


class NativeImageManager:
    def __init__(
        self,
        *,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        critics: Mapping[str, Sequence[object]],
    ):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.critics = {k: tuple(v) for k, v in critics.items()}
        self.engine = NativeImageEngine(artifact_dir=self.artifact_dir)

    def discover(self):
        return [self.engine.probe()]

    def status(self):
        return self.discover()

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        if request.media_type != "image":
            raise RuntimeError("FAP native image manager supports image generation only")
        observers = self.observer_bindings.get("image", ())
        critics = self.critics.get("image", ())
        if not observers:
            raise RuntimeError("no image observers configured")
        if not critics:
            raise RuntimeError("no image critics configured")

        lanes = [
            CandidateLane(
                self.engine.engine_id,
                self.engine,
                tuple(observers),
            )
        ]
        result = AdaptiveFastPathController(
            lanes,
            critics,
            initial_width=1,
            repair_width=1,
        ).run(request)
        return MediaSkillRun(
            result,
            (f"media.generate.image:{self.engine.engine_id}",),
        )
