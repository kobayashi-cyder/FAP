from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_generation import GenerationRequest
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObserverBinding

from .critic import SceneGraph2QualityCritic
from .engine import SceneGraph2Engine


class SceneGraph2Manager:
    def __init__(self, *, artifact_dir: str | Path, observer_bindings: Mapping[str, Sequence[ObserverBinding]], integrity_critics: Mapping[str, Sequence[object]]):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.integrity_critics = {k: tuple(v) for k, v in integrity_critics.items()}
        self.engine = SceneGraph2Engine(artifact_dir=self.artifact_dir)
        self.quality = SceneGraph2QualityCritic()

    def status(self):
        return [self.engine.probe()]

    def generate(self, request: GenerationRequest) -> MediaSkillRun:
        request.validate()
        lane = CandidateLane(
            self.engine.engine_id,
            self.engine,
            tuple(self.observer_bindings.get("image", ())),
        )
        result = AdaptiveFastPathController(
            [lane],
            tuple(self.integrity_critics.get("image", ())) + (self.quality,),
            initial_width=1,
            repair_width=1,
        ).run(request)
        if result.best_candidate is None:
            observed = [c for r in result.rounds for c in r.candidates]
            if observed:
                result = replace(
                    result,
                    best_candidate=max(
                        observed,
                        key=lambda x: (float(x.critique.score), x.backend_id),
                    ),
                )
        return MediaSkillRun(
            result,
            (f"media.generate.image:{self.engine.engine_id}",),
        )
