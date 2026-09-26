#!/usr/bin/env python3
from __future__ import annotations

import os
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

from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_media_lab.server import create_server
from fap_observed_media import ObserverBinding
from fap_scene_image import SceneImageManager, SceneMediaLabRuntime


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"

    host = os.environ.get("FAP_MEDIA_LAB_HOST", "127.0.0.1")
    port = int(os.environ.get("FAP_MEDIA_LAB_PORT", "11440"))
    runtime_dir = Path(
        os.environ.get(
            "FAP_MEDIA_LAB_RUNTIME",
            str(ROOT / "runtime" / "v87_31_scene_image"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)

    observer = ActualFileObserver()
    integrity = ArtifactIntegrityCritic()
    manager = SceneImageManager(
        artifact_dir=runtime_dir / "artifacts",
        observer_bindings={
            "image": (
                ObserverBinding("actual_file_evidence", observer, ("image",)),
            ),
        },
        integrity_critics={"image": (integrity,)},
    )
    runtime = SceneMediaLabRuntime(runtime_dir=runtime_dir, manager=manager)

    server = create_server(
        host,
        port,
        runtime=runtime,
        web_file=ROOT / "web" / "FAP_Media_Lab_V87_31.html",
    )
    print("FAP V87.31 SCENE IMAGE LAB")
    print(f"UI: http://{host}:{port}/")
    print("Pipeline: prompt -> scene graph -> human/dog geometry -> render -> integrity + scene/style gate")
    print("Photorealistic capability: NOT YET AVAILABLE; photo requests are rejected instead of falsely accepted")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
