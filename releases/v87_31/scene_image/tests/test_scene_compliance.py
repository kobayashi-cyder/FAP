from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_scene_image import (
    SceneImageEngine,
    SceneImageManager,
    SceneQualityCritic,
    build_dog_mesh,
    parse_scene_plan,
)


def request(prompt: str, constraints=(), attempts=1):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=192,
        height=256,
        max_attempts=attempts,
        min_score=0.99,
        constraints=tuple(constraints),
    )


def test_scene_parser_detects_human_dog_photo_and_center():
    plan = parse_scene_plan("人と犬", ("被写体を中央に保つ", "写真風"))
    assert plan.required_objects == ("human", "dog")
    assert plan.supported_objects == ("human", "dog")
    assert plan.unsupported_objects == ()
    assert "photorealistic" in plan.requested_styles
    assert plan.centered_subjects is True


def test_native_dog_has_real_geometry():
    dog = build_dog_mesh()
    assert len(dog.vertices) > 300
    assert len(dog.faces) > 500
    assert all(not v.weights for v in dog.vertices)


def test_human_and_dog_are_both_structurally_generated(tmp_path: Path):
    engine = SceneImageEngine(artifact_dir=tmp_path)
    req = request("人と犬", ("被写体を中央に保つ",))
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)

    assert Path(artifact.locator).is_file()
    assert Path(artifact.locator).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert artifact.metadata["generated_objects"] == ["human", "dog"]
    assert artifact.metadata["scene_required_objects"] == ["human", "dog"]
    assert artifact.metadata["unsupported_objects"] == []
    assert "centered_subjects" in artifact.metadata["applied_constraints"]
    assert artifact.metadata["scene_details"]["dog"]["geometry"] == "native-quadruped-beagle-like"


def test_scene_critic_rejects_missing_required_dog(tmp_path: Path):
    path = tmp_path / "x.png"
    path.write_bytes(b"not-a-real-png-but-not-used-by-this-critic")
    artifact = MediaArtifact(
        media_type="image",
        digest="abcd",
        mime_type="image/png",
        locator=str(path),
        metadata={
            "generated_objects": ["human"],
            "requested_styles": ["geometric-3d"],
            "render_style": "geometric-3d",
            "applied_constraints": [],
        },
    )
    critique = SceneQualityCritic().critique(request("人と犬"), artifact)
    assert critique.score == 0.0
    assert critique.has_fatal
    assert any(x.code == "missing_required_object" for x in critique.issues)
    assert critique.evidence["object_score"] == 0.0


def test_photo_request_is_not_falsely_accepted_by_style_gate(tmp_path: Path):
    engine = SceneImageEngine(artifact_dir=tmp_path)
    req = request("人と犬", ("写真風",))
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)
    critique = SceneQualityCritic().critique(req, artifact)

    assert set(artifact.metadata["generated_objects"]) == {"human", "dog"}
    assert artifact.metadata["render_style"] == "geometric-3d"
    assert critique.evidence["object_score"] == 1.0
    assert critique.evidence["style_score"] == 0.0
    assert critique.score == 0.0
    assert critique.has_fatal
    assert any(x.code == "photorealistic_style_unavailable" for x in critique.issues)


def test_manager_accepts_structural_scene_without_false_photo_claim(tmp_path: Path):
    observer = ActualFileObserver()
    integrity = ArtifactIntegrityCritic()
    manager = SceneImageManager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", observer, ("image",)),)
        },
        integrity_critics={"image": (integrity,)},
    )

    ok = manager.generate(request("人と犬", ("被写体を中央に保つ",), attempts=1))
    assert ok.result.accepted
    assert ok.result.best_candidate is not None
    assert ok.result.best_candidate.critique.score == 1.0

    photo = manager.generate(request("人と犬", ("被写体を中央に保つ", "写真風"), attempts=1))
    assert not photo.result.accepted
    assert photo.result.status == "rejected"
    assert photo.result.best_candidate is not None
    codes = {x.code for x in photo.result.best_candidate.critique.issues}
    assert "photorealistic_style_unavailable" in codes


def test_unknown_required_object_fails_closed(tmp_path: Path):
    engine = SceneImageEngine(artifact_dir=tmp_path)
    req = request("人と猫")
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)
    critique = SceneQualityCritic().critique(req, artifact)

    assert "human" in artifact.metadata["generated_objects"]
    assert "cat" in artifact.metadata["unsupported_objects"]
    assert critique.has_fatal
    assert critique.evidence["missing_objects"] == ["cat"]
    assert any(x.code == "unsupported_scene_object" for x in critique.issues)
