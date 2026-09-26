from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_autonomous_media import MediaSkillRun
from fap_media_portfolio import CandidateLane

from .critic import ScientificGeometryCritic
from .engine import ScientificGeometryEngine


class ScientificGeometryManager:
    def __init__(self, *, artifact_dir: str | Path, observer_bindings: Mapping[str, Sequence[object]], integrity_critics: Mapping[str, Sequence[object]]):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.observer_bindings = {k: tuple(v) for k, v in observer_bindings.items()}
        self.integrity_critics = {k: tuple(v) for k, v in integrity_critics.items()}
        self.engine = ScientificGeometryEngine(artifact_dir=self.artifact_dir)
        self.quality = ScientificGeometryCritic()

    def status(self):
        return [self.engine.probe()]

    def generate(self, request):
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
            candidates = [c for r in result.rounds for c in r.candidates]
            if candidates:
                result = replace(result, best_candidate=max(
                    candidates, key=lambda x: (float(x.critique.score), x.backend_id)
                ))
        return MediaSkillRun(result, (f"media.generate.image:{self.engine.engine_id}",))
