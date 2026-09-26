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
    ROOT / "releases" / "v87_32" / "photo_look",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_media_generation import GenerationRequest
from fap_photo_look import PhotoLookEngine, PhotoLookQualityCritic
from fap_scene_image import SceneImageEngine


def main():
    out = ROOT / "runtime" / "v87_32_photo_look_demo"
    out.mkdir(parents=True, exist_ok=True)
    req = GenerationRequest(
        prompt="人と犬",
        media_type="image",
        width=384,
        height=480,
        max_attempts=1,
        min_score=0.99,
        constraints=("被写体を中央に保つ",),
    )

    baseline_engine = SceneImageEngine(artifact_dir=out / "baseline_artifacts")
    photo_engine = PhotoLookEngine(artifact_dir=out / "photo_artifacts")

    baseline = baseline_engine.generate(
        req, prompt=req.prompt, previous=None, critique=None
    )
    improved = photo_engine.generate(
        req, prompt=req.prompt, previous=None, critique=None
    )

    (out / "v87_31_baseline.png").write_bytes(Path(baseline.locator).read_bytes())
    (out / "v87_32_photo_look.png").write_bytes(Path(improved.locator).read_bytes())

    photo_req = GenerationRequest(
        prompt="人と犬",
        media_type="image",
        width=384,
        height=480,
        max_attempts=1,
        min_score=0.99,
        constraints=("被写体を中央に保つ", "写真風"),
    )
    photo_requested = photo_engine.generate(
        photo_req, prompt=photo_req.prompt, previous=None, critique=None
    )
    critique = PhotoLookQualityCritic().critique(photo_req, photo_requested)
    (out / "v87_32_photo_requested.png").write_bytes(
        Path(photo_requested.locator).read_bytes()
    )

    result = {
        "baseline_style": baseline.metadata.get("render_style"),
        "improved_style": improved.metadata.get("render_style"),
        "generated_objects": improved.metadata.get("generated_objects"),
        "photo_look_features": improved.metadata.get("photo_look_features"),
        "photo_requested_score": critique.score,
        "photo_requested_fatal": critique.has_fatal,
        "photo_requested_issues": [x.code for x in critique.issues],
    }
    (out / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    print("V87.32 PHOTO-LOOK DEMO PASS")


if __name__ == "__main__":
    main()
