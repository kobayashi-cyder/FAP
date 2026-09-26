from __future__ import annotations

from dataclasses import dataclass

from fap_video_temporal import TemporalConsistencyCritic


@dataclass(frozen=True)
class Artifact:
    media_type: str
    metadata: dict


def track(object_id, x, appearance=(1.0, 0.0, 0.0)):
    return {
        "object_id": object_id,
        "x": x,
        "y": 100,
        "width": 80,
        "height": 80,
        "appearance": list(appearance),
        "confidence": 0.99,
    }


def frame(index, t, tracks, luminance=0.5):
    return {
        "index": index,
        "timestamp_s": t,
        "width": 1280,
        "height": 720,
        "luminance": luminance,
        "tracks": tracks,
    }


def artifact(frames, expected=("dog",)):
    return Artifact(
        "video",
        {"temporal_evidence": {"frames": frames, "expected_ids": list(expected)}},
    )


def test_stable_video_scores_perfect():
    a = artifact([
        frame(0, 0.0, [track("dog", 100)]),
        frame(1, 0.5, [track("dog", 120)]),
        frame(2, 1.0, [track("dog", 145)]),
    ])
    result = TemporalConsistencyCritic().critique(None, a)
    assert result.score == 1.0
    assert result.issues == ()


def test_identity_drift_is_high_severity():
    a = artifact([
        frame(0, 0.0, [track("dog", 100, (1.0, 0.0))]),
        frame(1, 0.5, [track("dog", 120, (0.0, 1.0))]),
    ])
    result = TemporalConsistencyCritic().critique(None, a)
    assert any(x.code == "identity_drift" and x.severity == "high" for x in result.issues)
    assert result.score < 1.0


def test_motion_jump_is_detected():
    a = artifact([
        frame(0, 0.0, [track("dog", 0)]),
        frame(1, 0.05, [track("dog", 1100)]),
    ])
    result = TemporalConsistencyCritic().critique(None, a)
    assert any(x.code == "motion_jump" for x in result.issues)


def test_subject_dropout_is_detected():
    a = artifact([
        frame(0, 0.0, [track("dog", 100)]),
        frame(1, 0.5, []),
        frame(2, 1.0, []),
        frame(3, 1.5, [track("dog", 130)]),
    ])
    result = TemporalConsistencyCritic(max_missing_ratio=0.20).critique(None, a)
    assert any(x.code == "subject_dropout" for x in result.issues)


def test_luminance_flicker_is_detected():
    a = artifact([
        frame(0, 0.0, [track("dog", 100)], 0.2),
        frame(1, 0.5, [track("dog", 110)], 0.9),
    ])
    result = TemporalConsistencyCritic().critique(None, a)
    assert any(x.code == "luminance_flicker" for x in result.issues)


def test_missing_evidence_fails_closed():
    a = Artifact("video", {})
    result = TemporalConsistencyCritic().critique(None, a)
    assert result.score == 0.0
    assert result.has_fatal


def test_non_video_fails_closed():
    a = Artifact("image", {"temporal_evidence": {}})
    result = TemporalConsistencyCritic().critique(None, a)
    assert result.has_fatal


def test_invalid_timestamps_fail_closed():
    a = artifact([
        frame(0, 0.5, [track("dog", 100)]),
        frame(1, 0.5, [track("dog", 110)]),
    ])
    result = TemporalConsistencyCritic().critique(None, a)
    assert result.has_fatal
    assert result.score == 0.0
