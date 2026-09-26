from __future__ import annotations

import json
import os
from pathlib import Path
import socket

import pytest

from fap_compact_offline import (
    CompactOfflineImageEngine,
    CompactOfflineError,
    discover_compact_models,
)
from fap_media_generation import GenerationRequest


class FakeImage:
    def save(self, path, format=None):
        Path(path).write_bytes(b"COMPACT-OFFLINE-PNG")


class Result:
    images = [FakeImage()]


class Pipe:
    def __init__(self):
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        return Result()


def make_model(tmp_path, *, license_id="apache-2.0"):
    model = tmp_path / "SSD-1B-A1111.safetensors"
    model.write_bytes(b"fake-checkpoint")
    config = tmp_path / "ssd1b-config"
    config.mkdir()
    (config / "model_index.json").write_text("{}", encoding="utf-8")
    sidecar = model.with_suffix(model.suffix + ".fap.json")
    sidecar.write_text(
        json.dumps(
            {
                "model_id": "segmind/SSD-1B",
                "license_id": license_id,
                "source": "https://huggingface.co/segmind/SSD-1B",
                "config_dir": "ssd1b-config",
                "distilled": True,
                "distillation_kind": "knowledge-distillation",
                "pipeline": "StableDiffusionXLPipeline",
                "inference_steps": 20,
            }
        ),
        encoding="utf-8",
    )
    return model


def test_compact_engine_generates_offline_png(tmp_path):
    model = make_model(tmp_path)
    pipe = Pipe()
    engine = CompactOfflineImageEngine(
        model,
        artifact_dir=tmp_path / "artifacts",
        loader=lambda model, config, manifest: pipe,
    )
    artifact = engine.generate(
        GenerationRequest("beagle", max_attempts=1),
        prompt="beagle",
        previous=None,
        critique=None,
    )
    assert artifact.mime_type == "image/png"
    assert Path(artifact.locator).read_bytes() == b"COMPACT-OFFLINE-PNG"
    assert artifact.metadata["distilled"] is True
    assert pipe.kwargs["num_inference_steps"] == 20


def test_network_is_blocked_inside_compact_inference(tmp_path):
    model = make_model(tmp_path)

    class NetworkPipe:
        def __call__(self, **kwargs):
            with pytest.raises(OSError, match="blocked"):
                socket.create_connection(("example.com", 443), timeout=0.01)
            return Result()

    engine = CompactOfflineImageEngine(
        model,
        artifact_dir=tmp_path / "artifacts",
        loader=lambda *args: NetworkPipe(),
    )
    engine.generate(
        GenerationRequest("x"),
        prompt="x",
        previous=None,
        critique=None,
    )


def test_restricted_license_is_rejected(tmp_path):
    model = make_model(tmp_path, license_id="noncommercial-only")
    with pytest.raises((ValueError, CompactOfflineError)):
        CompactOfflineImageEngine(model, artifact_dir=tmp_path / "out")


def test_discovery_requires_sidecar_manifest(tmp_path, monkeypatch):
    model = make_model(tmp_path)
    other = tmp_path / "other.safetensors"
    other.write_bytes(b"x")
    monkeypatch.setenv("FAP_OFFLINE_SINGLE_FILES", str(model) + os.pathsep + str(other))
    found = discover_compact_models()
    assert model.resolve() in found
    assert other.resolve() not in found


def test_probe_reports_compact_checkpoint_size(tmp_path):
    model = make_model(tmp_path)
    engine = CompactOfflineImageEngine(
        model,
        artifact_dir=tmp_path / "out",
        loader=lambda *args: Pipe(),
    )
    info = engine.probe()
    assert info["model_id"] == "segmind/SSD-1B"
    assert info["license_id"] == "apache-2.0"
    assert info["compact_single_file"] is True
    assert info["checkpoint_bytes"] == len(b"fake-checkpoint")
