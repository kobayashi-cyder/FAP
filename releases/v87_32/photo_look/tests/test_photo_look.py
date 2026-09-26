from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_photo_look import (
    PhotoLookEngine,
    PhotoLookManager,
    PhotoLookQualityCritic,
    augment_surface_details,
)
from fap_scene_image import SceneImageEngine
from fap_scene_image.scene import build_scene_geometry, parse_scene_plan


def request(prompt: str, constraints=(), attempts=1, width=160, height=208):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=width,
        height=height,
        max_attempts=attempts,
        min_score=0.99,
        constraints=tuple(constraints),
    )


def test_probe_declares_native_photo_look_without_external_weights(tmp_path: Path):
    info = PhotoLookEngine(artifact_dir=tmp_path).probe()
    assert info["engine_id"] == "fap-photo-look-v1"
    assert info["render_style"] == "photo-look-native"
    assert info["photo_look_capability"] == 0.58
    assert info["learned_refiner"] is False
    assert info["external_weights"] is False
    assert info["external_runtime"] is False
    assert info["stdlib_only"] is True


def test_surface_detail_adds_face_and_hair_geometry():
    plan = parse_scene_plan("人と犬", ())
    mesh, positions, generated, details = build_scene_geometry(plan, "人と犬")
    before_vertices = len(mesh.vertices)
    before_positions = len(positions)

    added = augment_surface_details(
        mesh,
        positions,
        generated_objects=generated,
        scene_details=details,
    )

    assert added["human_face_detail"] is True
    assert added["human_hair_detail"] is True
    assert len(mesh.vertices) > before_vertices + 150
    assert len(positions) == len(mesh.vertices)
    assert len(positions) > before_positions


def test_photo_look_engine_generates_human_and_dog_with_finish_features(tmp_path: Path):
    engine = PhotoLookEngine(artifact_dir=tmp_path)
    req = request("人と犬", ("被写体を中央に保つ",))
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)

    path = Path(artifact.locator)
    assert path.is_file()
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert set(artifact.metadata["generated_objects"]) == {"human", "dog"}
    assert artifact.metadata["render_style"] == "photo-look-native"
    assert artifact.metadata["photorealistic_verified"] is False
    features = set(artifact.metadata["photo_look_features"])
    assert {
        "smooth_vertex_normals",
        "material_profiles",
        "micro_surface_variation",
        "contact_shadows",
        "fxaa",
        "filmic_finish",
        "human_face_detail",
        "human_hair_detail",
    }.issubset(features)


def test_photo_look_output_is_not_v87_31_flat_output(tmp_path: Path):
    req = request("人と犬", ("被写体を中央に保つ",))
    old_engine = SceneImageEngine(artifact_dir=tmp_path / "old")
    new_engine = PhotoLookEngine(artifact_dir=tmp_path / "new")

    old = old_engine.generate(req, prompt=req.prompt, previous=None, critique=None)
    new = new_engine.generate(req, prompt=req.prompt, previous=None, critique=None)

    assert old.digest != new.digest
    assert old.metadata["render_style"] == "geometric-3d"
    assert new.metadata["render_style"] == "photo-look-native"
    assert len(Path(new.locator).read_bytes()) > 1500


def test_photo_request_gets_partial_style_progress_but_still_fails_closed(tmp_path: Path):
    engine = PhotoLookEngine(artifact_dir=tmp_path)
    req = request("人と犬", ("写真風",))
    artifact = engine.generate(req, prompt=req.prompt, previous=None, critique=None)
    critique = PhotoLookQualityCritic().critique(req, artifact)

    assert critique.evidence["object_score"] == 1.0
    assert critique.evidence["style_score"] == 0.58
    assert critique.evidence["photorealistic_verified"] is False
    assert critique.has_fatal
    assert critique.score == 0.58
    assert any(x.code == "photorealism_not_yet_verified" for x in critique.issues)


def test_manager_accepts_structural_scene_but_rejects_photo_claim(tmp_path: Path):
    manager = PhotoLookManager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (
                ObserverBinding("actual_file_evidence", ActualFileObserver(), ("image",)),
            ),
        },
        integrity_critics={"image": (ArtifactIntegrityCritic(),)},
    )

    structural = manager.generate(
        request("人と犬", ("被写体を中央に保つ",), attempts=1)
    )
    assert structural.result.accepted
    assert structural.result.best_candidate is not None
    assert structural.result.best_candidate.critique.score == 1.0

    photo = manager.generate(
        request("人と犬", ("被写体を中央に保つ", "写真風"), attempts=1)
    )
    assert not photo.result.accepted
    assert photo.result.best_candidate is not None
    # CompositeCritic is fail-closed: any fatal issue forces the aggregate
    # score to zero even though the style sub-critic reports measurable
    # photo-look progress.
    assert photo.result.best_candidate.critique.score == 0.0
    evidence = photo.result.best_candidate.critique.evidence
    quality = next(
        value for value in evidence.values()
        if isinstance(value, dict) and value.get("kind") == "photo-look-quality"
    )
    assert quality["style_score"] == 0.58
    assert quality["photo_look_capability"] == 0.58
    codes = {x.code for x in photo.result.best_candidate.critique.issues}
    assert "photorealism_not_yet_verified" in codes
