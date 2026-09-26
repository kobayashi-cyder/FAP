from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest

from fap_autonomous_media import (
    AutonomousMediaSkillManager,
    EngineConfig,
    EngineError,
    HTTPMediaEngine,
    MediaSkillRegistry,
    TransportResponse,
)
from fap_media_generation import Critique, GenerationRequest
from fap_observed_media import ObservationEnvelope, ObserverBinding


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout_s, max_bytes):
        self.calls.append((method, url, headers, body))
        if not self.responses:
            raise AssertionError("unexpected transport call")
        value = self.responses.pop(0)
        return TransportResponse(200, {"content-type": "application/json"}, json.dumps(value).encode())


def completed(mime, data):
    return {
        "status": "completed",
        "mime_type": mime,
        "data_base64": base64.b64encode(data).decode("ascii"),
    }


class FileObserver:
    def observe(self, request, artifact):
        data = Path(artifact.locator).read_bytes()
        return ObservationEnvelope(
            artifact.digest,
            {"byte_count": len(data)},
            observer_id="file-observer.v1",
            evidence_kind="actual-file",
        )


class PassCritic:
    def critique(self, request, artifact):
        evidence = artifact.metadata.get("actual_evidence", {})
        score = 0.95 if evidence.get("byte_count", 0) > 0 else 0.0
        return Critique(score, (), evidence={"actual_file": True})


def test_sync_image_engine_persists_real_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("IMG_TOKEN", "secret")
    transport = SequenceTransport([completed("image/png", b"PNG-BYTES")])
    engine = HTTPMediaEngine(
        EngineConfig("img", "image", "https://engine.example/generate", "IMG_TOKEN"),
        artifact_dir=tmp_path,
        transport=transport,
        sleep_fn=lambda _: None,
    )
    artifact = engine.generate(
        GenerationRequest("beagle"),
        prompt="beagle",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "image/png"
    assert Path(artifact.locator).read_bytes() == b"PNG-BYTES"
    assert len(artifact.digest) == 64
    assert "secret" not in str(artifact.metadata)


def test_async_video_engine_polls_and_persists_mp4(tmp_path, monkeypatch):
    monkeypatch.setenv("VID_TOKEN", "secret")
    transport = SequenceTransport([
        {"status": "queued", "job_id": "1", "poll_url": "https://engine.example/jobs/1"},
        {"status": "running", "job_id": "1", "poll_url": "https://engine.example/jobs/1"},
        completed("video/mp4", b"MP4-BYTES"),
    ])
    engine = HTTPMediaEngine(
        EngineConfig(
            "vid", "video", "https://engine.example/generate", "VID_TOKEN",
            poll_interval_s=0.0,
        ),
        artifact_dir=tmp_path,
        transport=transport,
        sleep_fn=lambda _: None,
    )
    artifact = engine.generate(
        GenerationRequest(
            "running dog",
            media_type="video",
            duration_s=3.0,
            fps=24,
        ),
        prompt="running dog",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "video/mp4"
    assert Path(artifact.locator).read_bytes() == b"MP4-BYTES"
    assert artifact.metadata["polls"] == 2
    assert [x[0] for x in transport.calls] == ["POST", "GET", "GET"]


def test_cross_origin_poll_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("VID_TOKEN", "secret")
    transport = SequenceTransport([
        {"status": "queued", "poll_url": "https://evil.example/jobs/1"},
    ])
    engine = HTTPMediaEngine(
        EngineConfig("vid", "video", "https://engine.example/generate", "VID_TOKEN"),
        artifact_dir=tmp_path,
        transport=transport,
        sleep_fn=lambda _: None,
    )
    with pytest.raises(EngineError):
        engine.generate(
            GenerationRequest("x", media_type="video", duration_s=1.0, fps=24),
            prompt="x",
            previous=None,
            critique=None,
        )


def test_registry_promotes_after_three_distinct_verified_successes(tmp_path):
    registry = MediaSkillRegistry(tmp_path / "registry.json")
    record = registry.register_engine(
        EngineConfig("img", "image", "https://engine.example/generate", "IMG_TOKEN")
    )
    assert record.stage == "candidate"
    stages = []
    for i, score in enumerate((0.90, 0.92, 0.95), start=1):
        record = registry.record_outcome(
            record.skill_id,
            digest=f"digest-{i}",
            score=score,
            passed=True,
            independent=True,
            reason="pass",
        )
        stages.append(record.stage)
    assert stages == ["testing", "shadow", "active"]


def test_duplicate_digest_does_not_fake_promotion(tmp_path):
    registry = MediaSkillRegistry(tmp_path / "registry.json")
    record = registry.register_engine(
        EngineConfig("img", "image", "https://engine.example/generate", "IMG_TOKEN")
    )
    for _ in range(3):
        record = registry.record_outcome(
            record.skill_id,
            digest="same-digest",
            score=0.99,
            passed=True,
            independent=True,
            reason="pass",
        )
    assert record.verified_successes == 1
    assert record.stage == "testing"


def test_environment_discovery_registers_image_and_video_without_secret_values(tmp_path, monkeypatch):
    registry = MediaSkillRegistry(tmp_path / "registry.json")
    monkeypatch.setenv(
        "FAP_MEDIA_ENGINES_JSON",
        json.dumps([
            {
                "engine_id": "img",
                "media_type": "image",
                "endpoint": "https://img.example/generate",
                "token_env": "IMG_TOKEN",
            },
            {
                "engine_id": "vid",
                "media_type": "video",
                "endpoint": "https://vid.example/generate",
                "token_env": "VID_TOKEN",
            },
        ]),
    )
    discovered = MediaSkillRegistry.discover_from_environment(registry)
    assert len(discovered) == 2
    raw = (tmp_path / "registry.json").read_text()
    assert "IMG_TOKEN" in raw and "VID_TOKEN" in raw
    assert "secret" not in raw


def test_manager_generates_and_self_promotes_image_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("IMG_TOKEN", "secret")
    registry = MediaSkillRegistry(tmp_path / "registry.json")
    record = registry.register_engine(
        EngineConfig("img", "image", "https://engine.example/generate", "IMG_TOKEN")
    )
    responses = [
        completed("image/png", b"IMG-ONE"),
        completed("image/png", b"IMG-TWO"),
        completed("image/png", b"IMG-THREE"),
    ]
    transport = SequenceTransport(responses)
    manager = AutonomousMediaSkillManager(
        registry,
        artifact_dir=tmp_path / "artifacts",
        observer_bindings={
            "image": (ObserverBinding("actual_evidence", FileObserver(), ("image",)),),
        },
        critics={"image": (PassCritic(),)},
        transports={"img": transport},
        sleep_fn=lambda _: None,
    )
    for _ in range(3):
        run = manager.generate(GenerationRequest("beagle", min_score=0.9))
        assert run.result.accepted
    assert registry.records[record.skill_id].stage == "active"


def test_manager_generates_video_through_async_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("VID_TOKEN", "secret")
    registry = MediaSkillRegistry()
    registry.register_engine(
        EngineConfig(
            "vid", "video", "https://engine.example/generate", "VID_TOKEN",
            poll_interval_s=0.0,
        )
    )
    transport = SequenceTransport([
        {"status": "queued", "poll_url": "https://engine.example/jobs/9"},
        completed("video/mp4", b"VIDEO-DATA"),
    ])
    manager = AutonomousMediaSkillManager(
        registry,
        artifact_dir=tmp_path / "artifacts",
        observer_bindings={
            "video": (ObserverBinding("actual_evidence", FileObserver(), ("video",)),),
        },
        critics={"video": (PassCritic(),)},
        transports={"vid": transport},
        sleep_fn=lambda _: None,
    )
    run = manager.generate(
        GenerationRequest(
            "beagle running on beach",
            media_type="video",
            duration_s=4.0,
            fps=24,
            min_score=0.9,
        )
    )
    assert run.result.accepted
    assert Path(run.result.best_candidate.artifact.locator).read_bytes() == b"VIDEO-DATA"


def test_manager_fails_closed_without_engine(tmp_path):
    manager = AutonomousMediaSkillManager(
        MediaSkillRegistry(),
        artifact_dir=tmp_path,
        observer_bindings={},
        critics={},
    )
    with pytest.raises(RuntimeError, match="no image generation engines"):
        manager.generate(GenerationRequest("beagle"))
