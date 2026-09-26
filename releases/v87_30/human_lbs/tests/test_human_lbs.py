from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import struct

from fap_human_lbs import (
    HumanLBSEngine,
    HumanLBSManager,
    Pose,
    build_human_mesh,
    default_human_skeleton,
    render_human_png,
    skinned_positions,
)
from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding


def req(prompt: str, width=192, height=256):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=width,
        height=height,
        max_attempts=2,
        min_score=0.99,
    )


def test_parent_rotation_moves_descendants():
    sk = default_human_skeleton()
    bind_elbow = sk.bind_joint("l_elbow")
    bind_wrist = sk.bind_joint("l_wrist")
    pose = Pose({"l_shoulder": (0.0, 0.0, 90.0)})
    elbow = sk.posed_joint("l_elbow", pose)
    wrist = sk.posed_joint("l_wrist", pose)

    assert elbow[1] > bind_elbow[1] + 0.4
    assert wrist[1] > bind_wrist[1] + 0.8
    assert abs(elbow[0] - sk.bind_joint("l_shoulder")[0]) < 0.08


def test_mesh_has_real_multi_bone_lbs_weights():
    sk = default_human_skeleton()
    mesh = build_human_mesh(sk)
    multi = [v for v in mesh.vertices if len(v.weights) > 1]

    assert len(sk.bones) >= 20
    assert len(mesh.vertices) > 500
    assert len(mesh.faces) > 900
    assert len(multi) > 40
    assert all(abs(sum(w for _, w in v.weights) - 1.0) < 1e-6 for v in mesh.vertices)


def test_lbs_deforms_weighted_surface():
    sk = default_human_skeleton()
    mesh = build_human_mesh(sk)
    bind = [v.bind_position for v in mesh.vertices]
    posed = skinned_positions(
        mesh,
        sk,
        Pose({
            "l_shoulder": (0.0, 0.0, 78.0),
            "l_elbow": (0.0, 0.0, 62.0),
        }),
    )
    deltas = [
        ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5
        for a, b in zip(bind, posed)
    ]
    assert max(deltas) > 0.5
    assert sum(1 for d in deltas if d > 0.05) > 60


def test_software_renderer_writes_valid_png():
    sk = default_human_skeleton()
    mesh = build_human_mesh(sk)
    data = render_human_png(
        mesh,
        sk,
        Pose({"r_shoulder": (0.0, 0.0, -82.0), "r_elbow": (0.0, 0.0, -70.0)}),
        width=192,
        height=256,
        yaw_deg=35.0,
    )
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (192, 256)
    assert len(data) > 1200


def test_engine_changes_pose_and_view_from_prompt(tmp_path: Path):
    engine = HumanLBSEngine(artifact_dir=tmp_path)
    a = engine.generate(
        req("正面で直立、腕を下げる"),
        prompt="正面で直立、腕を下げる",
        previous=None,
        critique=None,
    )
    b = engine.generate(
        req("斜めから、右腕を上げて手を振る"),
        prompt="斜めから、右腕を上げて手を振る",
        previous=None,
        critique=None,
    )
    assert a.digest != b.digest
    assert Path(a.locator).is_file()
    assert Path(b.locator).is_file()
    assert sha256(Path(a.locator).read_bytes()).hexdigest() == a.digest
    assert b.metadata["pose_bones"]
    assert b.metadata["view_yaw_deg"] == 35.0


def test_engine_declares_native_lbs_capability(tmp_path: Path):
    info = HumanLBSEngine(artifact_dir=tmp_path).probe()
    assert info["generation_kind"] == "skeletal-linear-blend-skinning"
    assert info["external_weights"] is False
    assert info["external_runtime"] is False
    assert info["stdlib_only"] is True
    assert info["multi_bone_vertices"] > 40


def test_manager_passes_existing_integrity_gate(tmp_path: Path):
    observer = ActualFileObserver()
    critic = ArtifactIntegrityCritic()
    manager = HumanLBSManager(
        artifact_dir=tmp_path,
        observer_bindings={
            "image": (ObserverBinding("actual_file_evidence", observer, ("image",)),)
        },
        critics={"image": (critic,)},
    )
    run = manager.generate(req("斜めから、右腕を上げて手を振る"))
    assert run.result.accepted
    assert run.result.generator_calls == 1
    assert run.result.best_candidate is not None
    candidate = run.result.best_candidate
    assert candidate.critique.score == 1.0
    assert Path(candidate.artifact.locator).is_file()
