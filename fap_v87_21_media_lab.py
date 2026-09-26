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
    ROOT / "releases" / "v87_21" / "local_engine",
]
for path in reversed(PATHS):
    sys.path.insert(0, str(path))

from fap_autonomous_media import MediaSkillRegistry
from fap_local_media import HybridAutonomousMediaSkillManager, LocalSkillStateStore
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic, MediaLabRuntime
from fap_media_lab.server import create_server
from fap_observed_media import ObserverBinding


def main():
    host = os.environ.get("FAP_MEDIA_LAB_HOST", "127.0.0.1")
    port = int(os.environ.get("FAP_MEDIA_LAB_PORT", "11440"))
    runtime_dir = Path(
        os.environ.get(
            "FAP_MEDIA_LAB_RUNTIME",
            str(ROOT / "runtime" / "v87_21_media_lab"),
        )
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = runtime_dir / "artifacts"

    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    registry = MediaSkillRegistry(runtime_dir / "media_skills.json")
    local_store = LocalSkillStateStore(runtime_dir / "local_media_skills.json")
    manager = HybridAutonomousMediaSkillManager(
        registry,
        local_store=local_store,
        artifact_dir=artifact_dir,
        observer_bindings={
            "image": (
                ObserverBinding("actual_file_evidence", observer, ("image",)),
            ),
            "video": (
                ObserverBinding("actual_file_evidence", observer, ("video",)),
            ),
        },
        critics={
            "image": (critic,),
            "video": (critic,),
        },
    )
    runtime = MediaLabRuntime(
        runtime_dir=runtime_dir,
        registry=registry,
        manager=manager,
    )

    # V87.20 runtime understands the old registry directly. V87.21 exposes
    # hybrid local/remote skill status by overriding status only at the boundary.
    base_status = runtime.status

    def hybrid_status():
        status = base_status()
        skills = manager.skill_status()
        status["version"] = "87.21"
        status["skills"] = skills
        status["state"] = "ready" if skills else "needs_engine"
        status["local_autodiscovery"] = {
            "enabled": True,
            "candidates": list(manager.discovery.candidates),
            "supported": "AUTOMATIC1111 / Forge-compatible /sdapi/v1/txt2img",
        }
        return status

    runtime.status = hybrid_status  # host boundary override, not persisted skill code

    web_file = ROOT / "web" / "FAP_Media_Lab.html"
    server = create_server(host, port, runtime=runtime, web_file=web_file)
    print("FAP V87.21 MEDIA LAB + LOCAL IMAGE ENGINE AUTODISCOVERY")
    print(f"UI: http://{host}:{port}/")
    print("Auto-detect: 127.0.0.1:7860, 127.0.0.1:7861, localhost:7860")
    print("Compatible local engine: AUTOMATIC1111 / Forge API")
    print("Qwen: not used")
    server.serve_forever()


if __name__ == "__main__":
    main()
