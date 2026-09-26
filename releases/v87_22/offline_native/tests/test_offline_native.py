from __future__ import annotations

import json
import os
from pathlib import Path
import socket

import pytest

from fap_media_generation import GenerationRequest
from fap_offline_native import OfflineDiffusersEngine, OfflineEngineError, load_manifest


class FakeImage:
    def save(self, path, format=None):
        Path(path).write_bytes(b"OFFLINE-PNG")


class FakeImageResult:
    images = [FakeImage()]


class FakeVideoResult:
    frames = [[b"frame1", b"frame2"]]


class RecordingPipe:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"
        return self.result


def write_model(tmp_path, *, media_type="image", license_id="apache-2.0", model_id="black-forest-labs/FLUX.1-schnell"):
    model = tmp_path / "model"
    model.mkdir()
    (model / "model_index.json").write_text("{}", encoding="utf-8")
    (model / "fap_model_manifest.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "media_type": media_type,
                "license_id": license_id,
                "source": "local-test",
                "distilled": True,
                "distillation_kind": "timestep-distilled",
                "pipeline": "DiffusionPipeline",
                "inference_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    return model


def test_manifest_accepts_apache_distilled_model(tmp_path):
    model = write_model(tmp_path)
    manifest = load_manifest(model)
    assert manifest.license_id == "apache-2.0"
    assert manifest.distilled is True


def test_manifest_rejects_unknown_or_restricted_license(tmp_path):
    model = write_model(tmp_path, license_id="unknown-proprietary")
    with pytest.raises((ValueError, OfflineEngineError)):
        load_manifest(model)


def test_image_generation_works_with_no_network_fallback(tmp_path):
    model = write_model(tmp_path)
    pipe = RecordingPipe(FakeImageResult())
    engine = OfflineDiffusersEngine(
        model,
        artifact_dir=tmp_path / "artifacts",
        pipeline_loader=lambda path, manifest: pipe,
    )
    artifact = engine.generate(
        GenerationRequest("beagle", max_attempts=1),
        prompt="beagle",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "image/png"
    assert Path(artifact.locator).read_bytes() == b"OFFLINE-PNG"
    assert artifact.metadata["offline"] is True
    assert artifact.metadata["distilled"] is True
    assert pipe.kwargs["guidance_scale"] == 0.0
    assert pipe.kwargs["num_inference_steps"] == 4


def test_non_loopback_network_is_blocked_during_inference(tmp_path):
    model = write_model(tmp_path)

    class NetPipe:
        def __call__(self, **kwargs):
            with pytest.raises(OSError, match="blocked"):
                socket.create_connection(("example.com", 443), timeout=0.01)
            return FakeImageResult()

    engine = OfflineDiffusersEngine(
        model,
        artifact_dir=tmp_path / "artifacts",
        pipeline_loader=lambda path, manifest: NetPipe(),
    )
    engine.generate(
        GenerationRequest("x"),
        prompt="x",
        previous=None,
        critique=None,
    )


def test_video_generation_encodes_local_frames(tmp_path):
    model = write_model(
        tmp_path,
        media_type="video",
        model_id="local/permissive-video",
    )
    pipe = RecordingPipe(FakeVideoResult())

    def encoder(frames, path, fps):
        assert frames == [b"frame1", b"frame2"]
        assert fps == 8
        Path(path).write_bytes(b"OFFLINE-MP4")

    engine = OfflineDiffusersEngine(
        model,
        artifact_dir=tmp_path / "artifacts",
        pipeline_loader=lambda path, manifest: pipe,
        video_encoder=encoder,
    )
    artifact = engine.generate(
        GenerationRequest(
            "dog running",
            media_type="video",
            duration_s=0.25,
            fps=8,
            max_attempts=1,
        ),
        prompt="dog running",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "video/mp4"
    assert Path(artifact.locator).read_bytes() == b"OFFLINE-MP4"
    assert pipe.kwargs["num_frames"] == 2


def test_missing_manifest_fails_closed(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    with pytest.raises(OfflineEngineError, match="manifest"):
        OfflineDiffusersEngine(model, artifact_dir=tmp_path / "artifacts")
