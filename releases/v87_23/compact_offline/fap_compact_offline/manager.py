from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .single_file import CompactOfflineImageEngine, discover_compact_models


class CompactOfflineManager:
    def __init__(
        self,
        *,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        critics: Mapping[str, Sequence[object]],
        model_files: Sequence[str | Path] | None = None,
        engine_factory=None,
    ):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.critics = {k: tuple(v) for k, v in critics.items()}
        self.model_files = tuple(model_files) if model_files is not None else None
        self.engine_factory = engine_factory or self._make_engine
        self.engines = {}

    def _make_engine(self, path):
        return CompactOfflineImageEngine(path, artifact_dir=self.artifact_dir)

    def discover(self):
        files = discover_compact_models(self.model_files)
        rows = []
        self.engines = {}
        for file in files:
            try:
                engine = self.engine_factory(file)
                info = engine.probe()
            except Exception:
                continue
            self.engines[engine.engine_id] = engine
            rows.append(info)
        return rows

    def status(self):
        return self.discover()

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        if request.media_type != "image":
            raise RuntimeError("compact offline manager currently supports image generation only")
        infos = self.discover()
        observers = self.observer_bindings.get("image", ())
        critics = self.critics.get("image", ())
        if not observers:
            raise RuntimeError("no image observers configured")
        if not critics:
            raise RuntimeError("no image critics configured")
        lanes = [
            CandidateLane(
                info["engine_id"],
                self.engines[info["engine_id"]],
                tuple(observers),
            )
            for info in infos
        ]
        if not lanes:
            raise RuntimeError("no compact offline image model discovered")
        result = AdaptiveFastPathController(
            lanes,
            critics,
            initial_width=1,
            repair_width=1,
        ).run(request)
        return MediaSkillRun(
            result,
            tuple(f"media.generate.image:{lane.backend_id}" for lane in lanes),
        )
