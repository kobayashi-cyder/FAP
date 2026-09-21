from __future__ import annotations

from math import sqrt

from fap_media_generation import Critique, CritiqueIssue

from .evidence import ObjectTrack, VideoTemporalEvidence


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return None
    return dot / (na * nb)


class TemporalConsistencyCritic:
    """Independent structured critic for bounded video evidence.

    The critic does not decode video bytes itself. A production video observer
    supplies frame evidence sampled from the actual generated artifact.
    """

    def __init__(
        self,
        *,
        identity_similarity_floor: float = 0.82,
        max_normalized_speed_per_s: float = 1.50,
        luminance_jump_limit: float = 0.30,
        max_missing_ratio: float = 0.20,
    ):
        if not (0.0 <= identity_similarity_floor <= 1.0):
            raise ValueError("identity_similarity_floor out of bounds")
        if max_normalized_speed_per_s <= 0:
            raise ValueError("max_normalized_speed_per_s must be positive")
        if not (0.0 < luminance_jump_limit <= 1.0):
            raise ValueError("luminance_jump_limit out of bounds")
        if not (0.0 <= max_missing_ratio <= 1.0):
            raise ValueError("max_missing_ratio out of bounds")
        self.identity_similarity_floor = identity_similarity_floor
        self.max_normalized_speed_per_s = max_normalized_speed_per_s
        self.luminance_jump_limit = luminance_jump_limit
        self.max_missing_ratio = max_missing_ratio

    def critique(self, request, artifact) -> Critique:
        if getattr(artifact, "media_type", None) != "video":
            return Critique(
                0.0,
                (CritiqueIssue("media_type", "temporal critic requires video", "fatal"),),
                evidence={"temporal": "wrong-media-type"},
            )
        try:
            evidence = VideoTemporalEvidence.from_value(
                getattr(artifact, "metadata", {}).get("temporal_evidence")
            )
        except Exception as exc:
            return Critique(
                0.0,
                (
                    CritiqueIssue(
                        "temporal_evidence",
                        f"missing or invalid temporal evidence: {exc}",
                        "fatal",
                        "re-observe the generated video and attach bounded frame evidence",
                    ),
                ),
                evidence={"temporal": "invalid"},
            )

        issues: list[CritiqueIssue] = []
        identity_checks = 0
        identity_failures = 0
        motion_checks = 0
        motion_failures = 0
        flicker_failures = 0

        previous = evidence.frames[0]
        previous_tracks = {t.object_id: t for t in previous.tracks}
        for frame in evidence.frames[1:]:
            dt = frame.timestamp_s - previous.timestamp_s
            current_tracks = {t.object_id: t for t in frame.tracks}

            if abs(frame.luminance - previous.luminance) > self.luminance_jump_limit:
                flicker_failures += 1
                issues.append(
                    CritiqueIssue(
                        "luminance_flicker",
                        f"large luminance jump at frame {frame.index}",
                        "medium",
                        "stabilize exposure and lighting across adjacent frames",
                    )
                )

            for object_id in sorted(set(previous_tracks) & set(current_tracks)):
                a = previous_tracks[object_id]
                b = current_tracks[object_id]
                similarity = _cosine_similarity(a.appearance, b.appearance)
                if similarity is not None:
                    identity_checks += 1
                    if similarity < self.identity_similarity_floor:
                        identity_failures += 1
                        issues.append(
                            CritiqueIssue(
                                "identity_drift",
                                f"{object_id} appearance drift at frame {frame.index}: {similarity:.3f}",
                                "high",
                                f"preserve {object_id} identity, markings, clothing, face and proportions",
                            )
                        )

                motion_checks += 1
                ax, ay = a.center
                bx, by = b.center
                displacement = sqrt((bx - ax) ** 2 + (by - ay) ** 2)
                normalized_speed = displacement / max(1.0, frame.diagonal) / dt
                if normalized_speed > self.max_normalized_speed_per_s:
                    motion_failures += 1
                    issues.append(
                        CritiqueIssue(
                            "motion_jump",
                            f"{object_id} implausible jump at frame {frame.index}: {normalized_speed:.3f} diag/s",
                            "high",
                            f"make {object_id} motion continuous between adjacent frames",
                        )
                    )

            previous = frame
            previous_tracks = current_tracks

        total_frames = len(evidence.frames)
        for object_id in evidence.expected_ids:
            missing = sum(
                1 for frame in evidence.frames
                if object_id not in {track.object_id for track in frame.tracks}
            )
            ratio = missing / total_frames
            if ratio > self.max_missing_ratio:
                issues.append(
                    CritiqueIssue(
                        "subject_dropout",
                        f"{object_id} missing in {missing}/{total_frames} sampled frames",
                        "high",
                        f"keep {object_id} visible and consistently tracked throughout the shot",
                    )
                )

        high = sum(1 for issue in issues if issue.severity == "high")
        medium = sum(1 for issue in issues if issue.severity == "medium")
        penalty = min(0.95, high * 0.16 + medium * 0.06)
        score = max(0.0, 1.0 - penalty)

        return Critique(
            score,
            tuple(issues),
            evidence={
                "temporal": "observed",
                "sampled_frames": total_frames,
                "identity_checks": identity_checks,
                "identity_failures": identity_failures,
                "motion_checks": motion_checks,
                "motion_failures": motion_failures,
                "flicker_failures": flicker_failures,
            },
        )
