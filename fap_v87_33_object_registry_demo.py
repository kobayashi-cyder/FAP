#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
for p in reversed([
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
    ROOT / "releases" / "v87_33" / "object_registry",
]):
    sys.path.insert(0, str(p))

from fap_media_generation import GenerationRequest
from fap_object_registry import ObjectRegistryEngine, ObjectRegistryQualityCritic


def main():
    out = ROOT / "runtime" / "v87_33_bird_dog_demo"
    out.mkdir(parents=True, exist_ok=True)
    engine = ObjectRegistryEngine(artifact_dir=out / "artifacts")
    req = GenerationRequest(
        prompt="鳥と犬",
        media_type="image",
        width=512,
        height=640,
        max_attempts=1,
        min_score=0.99,
        constraints=("被写体を中央に保つ", "写真風"),
    )
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)
    critique = ObjectRegistryQualityCritic().critique(req, artifact)
    target = out / "bird_and_dog.png"
    target.write_bytes(Path(artifact.locator).read_bytes())
    result = {
        "generated_objects": artifact.metadata["generated_objects"],
        "requested_styles": artifact.metadata["requested_styles"],
        "object_score": critique.evidence["object_score"],
        "style_score": critique.evidence["style_score"],
        "issues": [x.code for x in critique.issues],
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    print("V87.33 BIRD+DOG DEMO PASS")


if __name__ == "__main__":
    main()
