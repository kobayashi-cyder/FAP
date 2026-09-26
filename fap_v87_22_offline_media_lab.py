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
    ROOT / "releases" / "v87_22" / "offline_native",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic, MediaLabRuntime
from fap_media_lab.server import create_server
from fap_observed_media import ObserverBinding
from fap_offline_native import OfflineNativeMediaManager


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
            str(ROOT / "runtime" / "v87_22_offline_media_lab"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)

    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = OfflineNativeMediaManager(
        artifact_dir=runtime_dir / "artifacts",
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", observer, ("image",)),),
            "video": (ObserverBinding("actual_file_evidence", observer, ("video",)),),
        },
        critics={
            "image": (critic,),
            "video": (critic,),
        },
    )
    runtime = MediaLabRuntime(
        runtime_dir=runtime_dir,
        manager=manager,
    )

    base_status = runtime.status

    def offline_status():
        status = base_status()
        models = manager.status()
        status["version"] = "87.22"
        status["skills"] = [
            {
                "skill_id": f"media.generate.{m['media_type']}:{m['engine_id']}",
                "engine_id": m["engine_id"],
                "media_type": m["media_type"],
                "stage": "offline-local",
                "score_ema": 0.0,
                "verified_successes": 0,
                "verified_failures": 0,
                "credential_present": True,
                "endpoint_origin": "local-files-only",
                "adapter": "offline-diffusers",
                "model_id": m["model_id"],
                "license_id": m["license_id"],
                "distilled": m["distilled"],
                "distillation_kind": m["distillation_kind"],
            }
            for m in models
        ]
        status["state"] = "ready" if models else "needs_model"
        status["offline"] = True
        status["network_fallback"] = False
        return status

    runtime.status = offline_status

    server = create_server(
        host,
        port,
        runtime=runtime,
        web_file=ROOT / "web" / "FAP_Media_Lab.html",
    )
    print("FAP V87.22 OFFLINE NATIVE MEDIA LAB")
    print(f"UI: http://{host}:{port}/")
    print("Model discovery: FAP_OFFLINE_MODEL_DIRS")
    print("Hub/network fallback: disabled")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
