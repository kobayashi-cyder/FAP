from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_object_registry import (
    ObjectRegistryEngine,
    ObjectRegistryManager,
    ObjectRegistryQualityCritic,
    build_scene_geometry,
    parse_scene_plan,
    supported_object_names,
)


def req(prompt: str, constraints=(), attempts=1):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=192,
        height=256,
        max_attempts=attempts,
        min_score=0.99,
        constraints=tuple(constraints),
    )


def test_registry_exposes_all_current_parser_objects():
    assert set(supported_object_names()) == {"human", "dog", "bird", "cat", "horse", "car"}


def test_bird_and_dog_are_both_supported_and_generated():
    plan = parse_scene_plan("鳥と犬", ())
    assert set(plan.required_objects) == {"bird", "dog"}
    assert set(plan.supported_objects) == {"bird", "dog"}
    assert plan.unsupported_objects == ()

    mesh, positions, generated, details = build_scene_geometry(plan, "鳥と犬")
    assert set(generated) == {"bird", "dog"}
    assert len(mesh.vertices) == len(positions)
    assert len(mesh.faces) > 700
    assert details["bird"]["geometry"] == "native-bird"
    assert details["dog"]["geometry"] == "native-dog"


def test_actual_photo_constraint_is_propagated():
    plan = parse_scene_plan("鳥と犬", ("被写体を中央に保つ", "写真風"))
    assert "photorealistic" in plan.requested_styles
    assert plan.centered_subjects is True


def test_engine_generates_bird_and_dog_png(tmp_path: Path):
    engine = ObjectRegistryEngine(artifact_dir=tmp_path)
    r = req("鳥と犬", ("被写体を中央に保つ",))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)

    assert Path(artifact.locator).is_file()
    assert Path(artifact.locator).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert set(artifact.metadata["generated_objects"]) == {"bird", "dog"}
    assert artifact.metadata["unsupported_objects"] == []
    assert "centered_subjects" in artifact.metadata["applied_constraints"]


def test_bird_dog_object_gate_passes_without_photo_claim(tmp_path: Path):
    engine = ObjectRegistryEngine(artifact_dir=tmp_path)
    r = req("鳥と犬", ("被写体を中央に保つ",))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)
    critique = ObjectRegistryQualityCritic().critique(r, artifact)

    assert critique.evidence["object_score"] == 1.0
    assert critique.evidence["layout_score"] == 1.0
    assert critique.score == 1.0
    assert not critique.has_fatal


def test_bird_dog_photo_request_rejects_for_style_not_missing_bird(tmp_path: Path):
    engine = ObjectRegistryEngine(artifact_dir=tmp_path)
    r = req("鳥と犬", ("被写体を中央に保つ", "写真風"))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)
    critique = ObjectRegistryQualityCritic().critique(r, artifact)

    assert set(critique.evidence["generated_objects"]) == {"bird", "dog"}
    assert critique.evidence["missing_objects"] == []
    assert critique.evidence["object_score"] == 1.0
    assert critique.evidence["style_score"] == 0.58
    assert any(x.code == "photorealism_not_yet_verified" for x in critique.issues)
    assert not any(x.code == "missing_required_object" for x in critique.issues)


def test_manager_exact_screenshot_case_has_no_bird_failure(tmp_path: Path):
    manager = ObjectRegistryManager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", ActualFileObserver(), ("image",)),)
        },
        integrity_critics={"image": (ArtifactIntegrityCritic(),)},
    )
    run = manager.generate(req("鳥と犬", ("被写体を中央に保つ", "写真風"), attempts=1))
    assert not run.result.accepted
    assert run.result.best_candidate is not None
    candidate = run.result.best_candidate
    codes = {x.code for x in candidate.critique.issues}
    assert "missing_required_object" not in codes
    assert "unsupported_scene_object" not in codes
    assert "photorealism_not_yet_verified" in codes


def test_all_registered_objects_build_without_unsupported_gap():
    for text, expected in (
        ("人", "human"),
        ("犬", "dog"),
        ("鳥", "bird"),
        ("猫", "cat"),
        ("馬", "horse"),
        ("車", "car"),
    ):
        plan = parse_scene_plan(text)
        assert plan.supported_objects == (expected,)
        mesh, positions, generated, _ = build_scene_geometry(plan, text)
        assert generated == (expected,)
        assert len(mesh.vertices) == len(positions)
