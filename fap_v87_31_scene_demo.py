#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PATHS = [
    ROOT / "releases" / "v87_13" / "media_generation",
    ROOT / "releases" / "v87_15" / "observed_media",
    ROOT / "releases" / "v87_16" / "media_portfolio",
    ROOT / "releases" / "v87_17" / "adaptive_fast_path",
    ROOT / "releases" / "v87_19" / "autonomous_media",
    ROOT / "releases" / "v87_20" / "media_lab",
    ROOT / "releases" / "v87_29" / "native_image",
    ROOT / "releases" / "v87_30" / "human_lbs",
    ROOT / "releases" / "v87_31" / "scene_image",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_scene_image import SceneImageManager


def main():
    out = ROOT / "runtime" / "v87_31_scene_demo"
    out.mkdir(parents=True, exist_ok=True)
    manager = SceneImageManager(
        artifact_dir=out / "artifacts",
        observer_bindings={
            "image": (
                ObserverBinding("actual_file_evidence", ActualFileObserver(), ("image",)),
            ),
        },
        integrity_critics={"image": (ArtifactIntegrityCritic(),)},
    )

    rows = []
    cases = (
        ("human_dog", ("被写体を中央に保つ",)),
        ("human_dog_photo_requested", ("被写体を中央に保つ", "写真風")),
    )
    for name, constraints in cases:
        req = GenerationRequest(
            prompt="人と犬",
            media_type="image",
            width=512,
            height=640,
            max_attempts=1,
            min_score=0.99,
            constraints=constraints,
        )
        run = manager.generate(req)
        candidate = run.result.best_candidate
        if candidate is None:
            raise RuntimeError("expected inspectable candidate")
        source = Path(candidate.artifact.locator)
        target = out / f"{name}.png"
        target.write_bytes(source.read_bytes())
        rows.append({
            "name": name,
            "accepted": run.result.accepted,
            "status": run.result.status,
            "score": candidate.critique.score,
            "issues": [x.code for x in candidate.critique.issues],
            "generated_objects": candidate.artifact.metadata.get("generated_objects", []),
            "render_style": candidate.artifact.metadata.get("render_style", ""),
            "file": target.name,
        })
    (out / "result.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(rows, ensure_ascii=False))
    print("V87.31 SCENE DEMO PASS")


if __name__ == "__main__":
    main()
