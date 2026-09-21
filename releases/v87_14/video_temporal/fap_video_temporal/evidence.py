from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ObjectTrack:
    object_id: str
    x: float
    y: float
    width: float
    height: float
    appearance: tuple[float, ...] = ()
    confidence: float = 1.0

    def validate(self) -> None:
        if not self.object_id:
            raise ValueError("object_id is required")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("track dimensions must be positive")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("track confidence out of bounds")
        if len(self.appearance) > 4096:
            raise ValueError("appearance vector too large")

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height / 2.0

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ObjectTrack":
        appearance = raw.get("appearance", ())
        if not isinstance(appearance, Sequence) or isinstance(appearance, (str, bytes, bytearray)):
            raise ValueError("appearance must be a sequence")
        return cls(
            object_id=str(raw.get("object_id", "")),
            x=float(raw.get("x", 0.0)),
            y=float(raw.get("y", 0.0)),
            width=float(raw.get("width", 0.0)),
            height=float(raw.get("height", 0.0)),
            appearance=tuple(float(v) for v in appearance),
            confidence=float(raw.get("confidence", 1.0)),
        )


@dataclass(frozen=True)
class FrameEvidence:
    index: int
    timestamp_s: float
    width: int
    height: int
    luminance: float
    tracks: tuple[ObjectTrack, ...]

    def validate(self) -> None:
        if self.index < 0:
            raise ValueError("frame index must be non-negative")
        if self.timestamp_s < 0:
            raise ValueError("timestamp must be non-negative")
        if self.width < 1 or self.height < 1:
            raise ValueError("frame dimensions must be positive")
        if not (0.0 <= self.luminance <= 1.0):
            raise ValueError("luminance out of bounds")
        ids: set[str] = set()
        for track in self.tracks:
            track.validate()
            if track.object_id in ids:
                raise ValueError("duplicate object_id in frame")
            ids.add(track.object_id)

    @property
    def diagonal(self) -> float:
        return sqrt(float(self.width * self.width + self.height * self.height))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FrameEvidence":
        tracks = raw.get("tracks", ())
        if not isinstance(tracks, Sequence) or isinstance(tracks, (str, bytes, bytearray)):
            raise ValueError("tracks must be a sequence")
        return cls(
            index=int(raw.get("index", 0)),
            timestamp_s=float(raw.get("timestamp_s", 0.0)),
            width=int(raw.get("width", 0)),
            height=int(raw.get("height", 0)),
            luminance=float(raw.get("luminance", 0.0)),
            tracks=tuple(ObjectTrack.from_mapping(x) for x in tracks),
        )


@dataclass(frozen=True)
class VideoTemporalEvidence:
    frames: tuple[FrameEvidence, ...]
    expected_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if len(self.frames) < 2:
            raise ValueError("at least two frame observations are required")
        previous_index = -1
        previous_ts = -1.0
        dims = None
        for frame in self.frames:
            frame.validate()
            if frame.index <= previous_index:
                raise ValueError("frame indexes must strictly increase")
            if frame.timestamp_s <= previous_ts:
                raise ValueError("timestamps must strictly increase")
            current_dims = (frame.width, frame.height)
            if dims is None:
                dims = current_dims
            elif current_dims != dims:
                raise ValueError("frame dimensions changed")
            previous_index = frame.index
            previous_ts = frame.timestamp_s
        if len(set(self.expected_ids)) != len(self.expected_ids):
            raise ValueError("expected_ids must be unique")

    @classmethod
    def from_value(cls, value: Any) -> "VideoTemporalEvidence":
        if isinstance(value, cls):
            value.validate()
            return value
        if not isinstance(value, Mapping):
            raise ValueError("temporal_evidence must be a mapping")
        frames = value.get("frames", ())
        expected = value.get("expected_ids", ())
        if not isinstance(frames, Sequence) or isinstance(frames, (str, bytes, bytearray)):
            raise ValueError("frames must be a sequence")
        if not isinstance(expected, Sequence) or isinstance(expected, (str, bytes, bytearray)):
            raise ValueError("expected_ids must be a sequence")
        result = cls(
            frames=tuple(FrameEvidence.from_mapping(x) for x in frames),
            expected_ids=tuple(str(x) for x in expected),
        )
        result.validate()
        return result
