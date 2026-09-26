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
    ROOT / "releases" / "v87_30" / "human_lbs",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_human_lbs import HumanLBSManager
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic, MediaLabRuntime
from fap_media_lab.server import create_server
from fap_observed_media import ObserverBinding


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
            str(ROOT / "runtime" / "v87_30_human_lbs"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)

    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = HumanLBSManager(
        artifact_dir=runtime_dir / "artifacts",
        observer_bindings={
            "image": (
                ObserverBinding("actual_file_evidence", observer, ("image",)),
            ),
        },
        critics={"image": (critic,)},
    )
    runtime = MediaLabRuntime(runtime_dir=runtime_dir, manager=manager)
    base_status = runtime.status

    def lbs_status():
        status = base_status()
        engines = manager.status()
        status["version"] = "87.30"
        status["skills"] = [
            {
                "skill_id": f"media.generate.image:{e['engine_id']}",
                "engine_id": e["engine_id"],
                "media_type": "image",
                "stage": "fap-native-3d-lbs",
                "score_ema": 0.0,
                "verified_successes": 0,
                "verified_failures": 0,
                "credential_present": True,
                "endpoint_origin": "none",
                "adapter": "fap-human-lbs",
                "model_id": e["model_id"],
                "license_id": e["license_id"],
                "external_weights": e["external_weights"],
                "external_runtime": e["external_runtime"],
                "stdlib_only": e["stdlib_only"],
                "bones": e["bones"],
                "vertices": e["vertices"],
                "faces": e["faces"],
                "multi_bone_vertices": e["multi_bone_vertices"],
            }
            for e in engines
        ]
        status["state"] = "ready"
        status["offline"] = True
        status["network_fallback"] = False
        status["external_model_required"] = False
        status["fap_owned_engine"] = True
        status["geometry"] = "skeletal mesh + linear blend skinning + z-buffer"
        return status

    runtime.status = lbs_status
    server = create_server(
        host,
        port,
        runtime=runtime,
        web_file=ROOT / "web" / "FAP_Media_Lab.html",
    )
    print("FAP V87.30 HUMAN LBS IMAGE LAB")
    print(f"UI: http://{host}:{port}/")
    print("Engine: skeleton -> bind pose -> LBS -> software 3D render -> PNG")
    print("External image checkpoint: not required")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
