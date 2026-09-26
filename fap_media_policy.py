from __future__ import annotations

import gc
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImageProfile:
    name: str
    width: int
    height: int
    steps: int
    guidance: float
    timeout_s: float
    enable_hr: bool = False
    hr_scale: float = 1.0
    denoising_strength: float = 0.35


IMAGE_PROFILES = {
    "draft": ImageProfile(
        "draft", 512, 512, 22, 7.0, 300.0, False, 1.0, 0.35
    ),
    "standard": ImageProfile(
        "standard", 768, 768, 38, 7.5, 480.0, False, 1.0, 0.35
    ),
    "high": ImageProfile(
        "high", 1024, 1024, 56, 8.0, 720.0, True, 1.25, 0.30
    ),
}


@dataclass(frozen=True)
class VideoProfile:
    name: str
    width: int
    height: int
    fps: int
    keyframes: int
    max_duration_s: int


VIDEO_PROFILES = {
    "draft": VideoProfile("draft", 384, 384, 10, 2, 6),
    "standard": VideoProfile("standard", 512, 512, 12, 4, 10),
    "high": VideoProfile("high", 640, 640, 16, 6, 12),
}


def quality_mode(text: str, default: str = "standard") -> str:
    raw = str(text or "")
    patterns = (
        r"\[FAP_MEDIA\s+quality=(draft|standard|high)\]",
        r"\bquality\s*[:=]\s*(draft|standard|high)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return match.group(1).lower()

    compact = raw.casefold()
    if any(token in compact for token in ("軽量", "draft", "preview", "高速")):
        return "draft"
    if any(token in compact for token in ("高品質", "高画質", "high quality", "hq")):
        return "high"
    return default if default in IMAGE_PROFILES else "standard"


def strip_control_directives(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\[FAP_MEDIA\s+[^\]]+\]", " ", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def image_profile(text: str) -> ImageProfile:
    return IMAGE_PROFILES[quality_mode(text)]


def video_profile(text: str) -> VideoProfile:
    return VIDEO_PROFILES[quality_mode(text)]


class ArtifactBudget:
    """Bound generated-file growth without touching pinned/current artifacts."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 48,
        max_bytes: int = 192 * 1024 * 1024,
    ) -> None:
        self.root = Path(root)
        self.max_files = max(4, int(max_files))
        self.max_bytes = max(16 * 1024 * 1024, int(max_bytes))

    def prune(self, keep: Iterable[str | Path] = ()) -> dict[str, int]:
        self.root.mkdir(parents=True, exist_ok=True)
        keep_paths = {Path(p).resolve() for p in keep if str(p)}
        rows = []
        for path in self.root.iterdir():
            try:
                if not path.is_file():
                    continue
                resolved = path.resolve()
                stat = path.stat()
                rows.append([path, resolved, int(stat.st_size), float(stat.st_mtime)])
            except OSError:
                continue

        rows.sort(key=lambda row: row[3], reverse=True)
        total = sum(row[2] for row in rows)
        removed = 0
        removed_bytes = 0
        retained = 0

        for index, row in enumerate(rows):
            path, resolved, size, _mtime = row
            must_keep = resolved in keep_paths
            over_count = index - removed >= self.max_files
            over_bytes = total - removed_bytes > self.max_bytes
            if must_keep or (not over_count and not over_bytes):
                retained += 1
                continue
            try:
                path.unlink()
                removed += 1
                removed_bytes += size
            except OSError:
                retained += 1

        return {
            "removed_files": removed,
            "removed_bytes": removed_bytes,
            "retained_files": retained,
        }


def release_transient_memory() -> dict[str, float | int]:
    started = time.perf_counter()
    collected = gc.collect()
    return {
        "gc_collected": int(collected),
        "gc_elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }
