from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .engine import OfflineDiffusersEngine, OfflineEngineError


class OfflineNativeMediaManager:
    """Discover fully local model directories and route them through FAP evidence gates."""

    def __init__(
        self,
        *,
        artifact_dir: str | Path,
        observer_bindings: Mapping[str, Sequence[ObserverBinding]],
        critics: Mapping[str, Sequence[object]],
        model_paths: Sequence[str | Path] | None = None,
        engine_factory=None,
    ):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.critics = {k: tuple(v) for k, v in critics.items()}
        self.model_paths = tuple(model_paths or self._env_paths())
        self.engine_factory = engine_factory or self._make_engine
        self.engines = {}

    def _env_paths(self):
        raw = os.environ.get("FAP_OFFLINE_MODEL_DIRS", "").strip()
        if not raw:
            return ()
        separator = ";" if os.name == "nt" else ":"
        return tuple(Path(x.strip()) for x in raw.split(separator) if x.strip())

    def _make_engine(self, path):
        return OfflineDiffusersEngine(path, artifact_dir=self.artifact_dir)

    def discover(self):
        found = []
        self.engines = {}
        for path in self.model_paths:
            try:
                engine = self.engine_factory(path)
                info = engine.probe()
            except Exception:
                continue
            self.engines[engine.engine_id] = engine
            found.append(info)
        return found

    def status(self):
        return self.discover()

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        infos = self.discover()
        observers = self.observer_bindings.get(request.media_type, ())
        critics = self.critics.get(request.media_type, ())
        if not observers:
            raise RuntimeError(f"no {request.media_type} observers configured")
        if not critics:
            raise RuntimeError(f"no {request.media_type} critics configured")

        lanes = []
        for info in infos:
            if info["media_type"] != request.media_type:
                continue
            engine = self.engines[info["engine_id"]]
            lanes.append(CandidateLane(engine.engine_id, engine, tuple(observers)))
        if not lanes:
            raise RuntimeError(f"no offline {request.media_type} model discovered")

        result = AdaptiveFastPathController(
            lanes,
            critics,
            initial_width=1,
            repair_width=1,
        ).run(request)
        return MediaSkillRun(
            result,
            tuple(
                f"media.generate.{request.media_type}:{lane.backend_id}"
                for lane in lanes
            ),
        )
