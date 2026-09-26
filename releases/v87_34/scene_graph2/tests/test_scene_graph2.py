from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_scene_graph2 import (
    SceneGraph2Engine,
    SceneGraph2Manager,
    SceneGraph2QualityCritic,
    parse_scene_graph,
)


PROMPT = "2羽の白い鳥が犬の上を飛んでいて、犬は鳥を見ている。側面から。"


def req(prompt=PROMPT, constraints=(), attempts=1):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=192,
        height=256,
        max_attempts=attempts,
        min_score=0.99,
        constraints=tuple(constraints),
    )


def test_parser_extracts_count_color_state_relations_view_and_negative():
    graph = parse_scene_graph(
        PROMPT,
        ("猫は入れない", "写真風"),
    )
    assert graph.required_counts == {"dog": 1, "bird": 2}
    birds = [n for n in graph.nodes if n.kind == "bird"]
    dogs = [n for n in graph.nodes if n.kind == "dog"]
    assert len(birds) == 2
    assert birds[0].attr_dict()["color"] == "white"
    assert birds[0].state == "flying"
    assert dogs[0].state == "default" or dogs[0].state == "standing"
    keys = {r.key() for r in graph.relations}
    assert "bird:above:dog" in keys
    assert "dog:looking_at:bird" in keys
    assert graph.viewpoint == "side"
    assert graph.forbidden_kinds == ("cat",)
    assert "photorealistic" in graph.requested_styles


def test_engine_generates_exact_counts_and_side_view(tmp_path: Path):
    engine = SceneGraph2Engine(artifact_dir=tmp_path)
    r = req(constraints=("猫は入れない",))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)

    assert Path(artifact.locator).is_file()
    assert artifact.metadata["generated_counts"] == {"dog": 1, "bird": 2}
    assert artifact.metadata["forbidden_kinds"] == ["cat"]
    assert artifact.metadata["applied_viewpoint"] == "side"
    assert artifact.metadata["view_yaw_deg"] == 88.0
    assert set(artifact.metadata["applied_relations"]) == {
        "bird:above:dog",
        "dog:looking_at:bird",
    }


def test_white_attribute_is_applied_to_both_birds(tmp_path: Path):
    engine = SceneGraph2Engine(artifact_dir=tmp_path)
    r = req()
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)

    birds = [n for n in artifact.metadata["generated_nodes"] if n["kind"] == "bird"]
    assert len(birds) == 2
    assert all(n["attributes"].get("color") == "white" for n in birds)
    assert all(n["state_applied"] is True for n in birds)


def test_scene_graph2_critic_passes_semantics_without_photo_request(tmp_path: Path):
    engine = SceneGraph2Engine(artifact_dir=tmp_path)
    r = req(constraints=("猫は入れない",))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)
    critique = SceneGraph2QualityCritic().critique(r, artifact)

    assert critique.score == 1.0
    assert not critique.has_fatal
    assert critique.evidence["count_score"] == 1.0
    assert critique.evidence["attribute_score"] == 1.0
    assert critique.evidence["relation_score"] == 1.0
    assert critique.evidence["negative_score"] == 1.0
    assert critique.evidence["viewpoint_score"] == 1.0


def test_photo_request_fails_only_style_after_scene_semantics_pass(tmp_path: Path):
    engine = SceneGraph2Engine(artifact_dir=tmp_path)
    r = req(constraints=("猫は入れない", "写真風"))
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)
    critique = SceneGraph2QualityCritic().critique(r, artifact)

    assert critique.evidence["count_score"] == 1.0
    assert critique.evidence["attribute_score"] == 1.0
    assert critique.evidence["relation_score"] == 1.0
    assert critique.evidence["negative_score"] == 1.0
    assert critique.evidence["viewpoint_score"] == 1.0
    assert critique.evidence["style_score"] == 0.58
    assert critique.has_fatal
    assert {i.code for i in critique.issues} == {"photorealism_not_yet_verified"}


def test_illustration_request_is_not_falsely_accepted(tmp_path: Path):
    engine = SceneGraph2Engine(artifact_dir=tmp_path)
    r = req(prompt="犬と鳥、アニメ風")
    artifact = engine.generate(r, prompt=r.prompt, previous=None, critique=None)
    critique = SceneGraph2QualityCritic().critique(r, artifact)

    assert critique.evidence["style_score"] == 0.0
    assert any(i.code == "illustration_style_unavailable" for i in critique.issues)


def test_manager_preserves_rejected_candidate_for_inspection(tmp_path: Path):
    manager = SceneGraph2Manager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", ActualFileObserver(), ("image",)),)
        },
        integrity_critics={"image": (ArtifactIntegrityCritic(),)},
    )
    run = manager.generate(req(constraints=("写真風",)))
    assert not run.result.accepted
    assert run.result.best_candidate is not None
