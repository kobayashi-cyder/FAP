from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import struct

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_native_image import NativeImageEngine, NativeImageManager
from fap_observed_media import ObserverBinding


def _request(prompt: str, width=128, height=96):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=width,
        height=height,
        max_attempts=2,
        min_score=0.99,
    )


def test_native_engine_writes_real_png_without_external_weights(tmp_path: Path):
    engine = NativeImageEngine(artifact_dir=tmp_path)
    artifact = engine.generate(
        _request("青い夜の山と月、湖と森"),
        prompt="青い夜の山と月、湖と森",
        previous=None,
        critique=None,
    )
    path = Path(artifact.locator)
    data = path.read_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (128, 96)
    assert sha256(data).hexdigest() == artifact.digest
    assert artifact.mime_type == "image/png"
    assert artifact.metadata["external_weights"] is False
    assert artifact.metadata["stdlib_only"] is True
    assert engine.probe()["external_runtime"] is False


def test_prompt_changes_generated_bytes(tmp_path: Path):
    engine = NativeImageEngine(artifact_dir=tmp_path)
    a = engine.generate(
        _request("夕焼けの海と山"),
        prompt="夕焼けの海と山",
        previous=None,
        critique=None,
    )
    b = engine.generate(
        _request("黒と紫の幾何学的な抽象模様"),
        prompt="黒と紫の幾何学的な抽象模様",
        previous=None,
        critique=None,
    )
    assert a.digest != b.digest


def test_manager_passes_existing_artifact_integrity_gate(tmp_path: Path):
    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = NativeImageManager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", observer, ("image",)),)
        },
        critics={"image": (critic,)},
    )
    run = manager.generate(_request("森の中の小屋と朝の太陽"))
    assert run.result.accepted
    assert run.result.generator_calls == 1
    assert run.result.best_candidate is not None
    artifact = run.result.best_candidate.artifact
    assert Path(artifact.locator).is_file()
    assert run.result.best_candidate.critique.score == 1.0


def test_probe_declares_no_checkpoint_requirement(tmp_path: Path):
    info = NativeImageEngine(artifact_dir=tmp_path).probe()
    assert info["engine_id"] == "fap-native-raster-v1"
    assert info["offline"] is True
    assert info["external_weights"] is False
    assert info["external_runtime"] is False
    assert info["generation_kind"] == "procedural-prompt-to-raster"
