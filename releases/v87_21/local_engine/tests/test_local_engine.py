from __future__ import annotations

import base64
import json
from pathlib import Path

from fap_local_media import (
    A1111Discovery,
    A1111LocalEngine,
    HybridAutonomousMediaSkillManager,
    LocalSkillStateStore,
    LocalTransportResponse,
)
from fap_autonomous_media import MediaSkillRegistry
from fap_media_generation import Critique, GenerationRequest
from fap_observed_media import ObservationEnvelope, ObserverBinding


class RouterTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body, timeout_s, max_bytes):
        self.calls.append((method, url, body))
        if url.endswith("/sdapi/v1/sd-models"):
            return LocalTransportResponse(
                200,
                {"content-type": "application/json"},
                json.dumps([{"title": "local-model"}]).encode(),
            )
        if url.endswith("/sdapi/v1/txt2img"):
            return LocalTransportResponse(
                200,
                {"content-type": "application/json"},
                json.dumps({
                    "images": [
                        base64.b64encode(b"REAL-LOCAL-PNG").decode("ascii")
                    ]
                }).encode(),
            )
        return LocalTransportResponse(404, {}, b"{}")


class Observer:
    def observe(self, request, artifact):
        data = Path(artifact.locator).read_bytes()
        return ObservationEnvelope(
            artifact.digest,
            {"bytes": len(data), "sha256": artifact.digest},
            observer_id="test-observer",
            evidence_kind="actual-file",
        )


class Critic:
    def critique(self, request, artifact):
        return Critique(1.0, (), evidence={"verified": True})


def test_a1111_probe_and_real_image_generation(tmp_path):
    transport = RouterTransport()
    engine = A1111LocalEngine(
        "http://127.0.0.1:7860",
        artifact_dir=tmp_path,
        transport=transport,
    )
    probe = engine.probe()
    assert probe.model_count == 1
    artifact = engine.generate(
        GenerationRequest("beagle"),
        prompt="beagle",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "image/png"
    assert Path(artifact.locator).read_bytes() == b"REAL-LOCAL-PNG"
    assert artifact.metadata["adapter"] == "a1111-local"


def test_discovery_only_accepts_loopback_candidates(tmp_path):
    transport = RouterTransport()
    discovery = A1111Discovery(
        artifact_dir=tmp_path,
        transport=transport,
        candidates=(
            "http://127.0.0.1:7860",
            "http://localhost:7860",
        ),
    )
    found = discovery.discover()
    assert len(found) == 2
    assert all(x[1].model_count == 1 for x in found)


def test_hybrid_manager_generates_without_api_key(tmp_path):
    transport = RouterTransport()
    registry = MediaSkillRegistry(tmp_path / "remote.json")
    local_store = LocalSkillStateStore(tmp_path / "local.json")
    manager = HybridAutonomousMediaSkillManager(
        registry,
        local_store=local_store,
        artifact_dir=tmp_path / "artifacts",
        observer_bindings={
            "image": (ObserverBinding("evidence", Observer(), ("image",)),),
        },
        critics={"image": (Critic(),)},
        local_transport=transport,
        local_candidates=("http://127.0.0.1:7860",),
    )
    run = manager.generate(GenerationRequest("beagle", max_attempts=1, min_score=0.9))
    assert run.result.accepted
    candidate = run.result.best_candidate
    assert candidate.backend_id == "a1111-local-1"
    assert Path(candidate.artifact.locator).read_bytes() == b"REAL-LOCAL-PNG"
    assert any(x.startswith("media.generate.image:a1111-local") for x in run.updated_skills)


def test_local_skill_promotes_after_three_distinct_images(tmp_path):
    store = LocalSkillStateStore(tmp_path / "local.json")
    record = store.ensure("a1111-local-1", "http://127.0.0.1:7860")
    stages = []
    for index in range(3):
        record = store.record(
            record.skill_id,
            digest=f"digest-{index}",
            score=1.0,
            passed=True,
        )
        stages.append(record.stage)
    assert stages == ["testing", "shadow", "active"]


def test_non_loopback_local_engine_is_rejected(tmp_path):
    try:
        A1111LocalEngine(
            "http://example.com:7860",
            artifact_dir=tmp_path,
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
