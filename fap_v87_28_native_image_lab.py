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
    ROOT / "releases" / "v87_28" / "native_image",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic, MediaLabRuntime
from fap_media_lab.server import create_server
from fap_native_image import NativeImageManager
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
            str(ROOT / "runtime" / "v87_28_native_image"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)

    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = NativeImageManager(
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

    def native_status():
        status = base_status()
        engines = manager.status()
        status["version"] = "87.28"
        status["skills"] = [
            {
                "skill_id": f"media.generate.image:{e['engine_id']}",
                "engine_id": e["engine_id"],
                "media_type": "image",
                "stage": "fap-native",
                "score_ema": 0.0,
                "verified_successes": 0,
                "verified_failures": 0,
                "credential_present": True,
                "endpoint_origin": "none",
                "adapter": "fap-native-raster",
                "model_id": e["model_id"],
                "license_id": e["license_id"],
                "external_weights": e["external_weights"],
                "external_runtime": e["external_runtime"],
                "stdlib_only": e["stdlib_only"],
                "generation_kind": e["generation_kind"],
            }
            for e in engines
        ]
        status["state"] = "ready"
        status["offline"] = True
        status["network_fallback"] = False
        status["external_model_required"] = False
        status["fap_owned_engine"] = True
        status["quality_scope"] = (
            "procedural/stylized prompt-to-raster; not a photorealistic diffusion model"
        )
        return status

    runtime.status = native_status
    server = create_server(
        host,
        port,
        runtime=runtime,
        web_file=ROOT / "web" / "FAP_Media_Lab.html",
    )
    print("FAP V87.28 NATIVE IMAGE ENGINE")
    print(f"UI: http://{host}:{port}/")
    print("External checkpoint: not required")
    print("External API: not used")
    print("Python packages: stdlib engine; FAP runtime only")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
