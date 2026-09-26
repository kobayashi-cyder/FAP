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
    ROOT / "releases" / "v87_23" / "compact_offline",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_compact_offline import CompactOfflineManager
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
            str(ROOT / "runtime" / "v87_23_compact_offline"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)

    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = CompactOfflineManager(
        artifact_dir=runtime_dir / "artifacts",
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", observer, ("image",)),),
        },
        critics={"image": (critic,)},
    )
    runtime = MediaLabRuntime(runtime_dir=runtime_dir, manager=manager)
    base_status = runtime.status

    def compact_status():
        status = base_status()
        models = manager.status()
        status["version"] = "87.23"
        status["skills"] = [
            {
                "skill_id": f"media.generate.image:{m['engine_id']}",
                "engine_id": m["engine_id"],
                "media_type": "image",
                "stage": "compact-offline",
                "score_ema": 0.0,
                "verified_successes": 0,
                "verified_failures": 0,
                "credential_present": True,
                "endpoint_origin": "local-single-file",
                "adapter": "compact-offline-single-file",
                "model_id": m["model_id"],
                "license_id": m["license_id"],
                "distilled": m["distilled"],
                "distillation_kind": m["distillation_kind"],
                "checkpoint_bytes": m["checkpoint_bytes"],
            }
            for m in models
        ]
        status["state"] = "ready" if models else "needs_model"
        status["offline"] = True
        status["network_fallback"] = False
        status["compact_single_file"] = True
        return status

    runtime.status = compact_status
    server = create_server(
        host,
        port,
        runtime=runtime,
        web_file=ROOT / "web" / "FAP_Media_Lab.html",
    )
    print("FAP V87.23 COMPACT OFFLINE MEDIA LAB")
    print(f"UI: http://{host}:{port}/")
    print("Autodiscovery: FAP_OFFLINE_SINGLE_FILES + common A1111/Forge model folders")
    print("Network fallback: disabled")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
