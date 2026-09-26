from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fap_fmg_image_module import FMGImportedImageModule
from fap_media_policy import release_transient_memory, strip_control_directives, video_profile


VIDEO_VERSION = "FAP-FMG-VIDEO-0.1"
DEFAULT_DURATION_SECONDS = 8
DEFAULT_FPS = 12
MAX_KEYFRAMES = 6


def _video_intent(text: str) -> bool:
    value = str(text or "").casefold()
    hints = (
        "動画生成",
        "動画を生成",
        "動画を作",
        "映像を生成",
        "映像を作",
        "video generate",
        "generate video",
        "create video",
        "make a video",
    )
    return any(token in value for token in hints)


def _duration_seconds(text: str) -> int:
    raw = str(text or "")
    patterns = (
        r"(?<!\d)(\d{1,2})\s*秒",
        r"(?<!\d)(\d{1,2})\s*(?:sec|secs|second|seconds)\b",
    )
    for pat in patterns:
        match = re.search(pat, raw, re.I)
        if match:
            try:
                return max(2, min(15, int(match.group(1))))
            except Exception:
                pass
    return DEFAULT_DURATION_SECONDS


class FMGImportedVideoModule:
    """Real video pipeline entry point for FAP.

    Phase 1 deliberately separates *visual generation* from *video encoding*:
    FMG creates temporal keyframes, then Android composes those frames into an
    H.264 MP4 using the platform MediaCodec encoder. This produces an actual
    video file on-device without pretending a full temporal-diffusion model is
    running on Pixel.

    When a stronger video model is added later, it can replace the keyframe
    producer while preserving the Android media artifact contract.
    """

    def __init__(
        self,
        root: str | Path,
        image_module: FMGImportedImageModule,
    ) -> None:
        self.root = Path(root).resolve()
        self.image_module = image_module
        self.keyframes = max(
            2,
            min(
                MAX_KEYFRAMES,
                int(os.environ.get("FAP_VIDEO_KEYFRAMES", str(MAX_KEYFRAMES))),
            ),
        )

    @staticmethod
    def matches(text: str) -> bool:
        return _video_intent(text)

    def status(self) -> dict[str, Any]:
        return {
            "version": VIDEO_VERSION,
            "mode": "fmg-keyframes+android-h264",
            "default_duration_seconds": DEFAULT_DURATION_SECONDS,
            "default_fps": DEFAULT_FPS,
            "keyframes": self.keyframes,
            "true_temporal_diffusion": False,
            "output_contract": "video_storyboard -> Android MediaCodec -> H.264 MP4",
        }

    def _scene_prompts(self, prompt: str, quality: str, keyframes: int) -> list[str]:
        suffixes = (
            "opening establishing shot, wide composition, coherent scene",
            "camera moves closer, medium-wide composition, preserve subjects and location",
            "mid-scene action, cinematic movement, preserve visual identity and environment",
            "closing shot, cinematic composition, preserve the same world and subjects",
        )
        out: list[str] = []
        expanded = list(suffixes)
        if keyframes > len(expanded):
            expanded.extend((
                "continuity bridge shot, preserve identity, lighting and scene geometry",
                "final cinematic hold, preserve identity, lighting and scene geometry",
            ))
        for suffix in expanded[:keyframes]:
            out.append(
                f"[FAP_MEDIA quality={quality}] 画像生成: "
                + prompt
                + "\nTemporal video keyframe: "
                + suffix
            )
        return out

    @staticmethod
    def _artifact_path(result: dict[str, Any]) -> str:
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list):
            return ""
        for row in artifacts:
            if not isinstance(row, dict):
                continue
            if str(row.get("type") or "") != "image":
                continue
            path = str(row.get("path") or "").strip()
            if path and Path(path).is_file():
                return path
        return ""

    def generate(self, text: str) -> dict[str, Any]:
        raw_prompt = str(text or "").strip()
        profile = video_profile(raw_prompt)
        prompt = strip_control_directives(raw_prompt)
        if not prompt:
            return {
                "ok": False,
                "reply": "動画生成プロンプトが空です。",
                "confidence": 1.0,
            }

        duration = min(_duration_seconds(prompt), profile.max_duration_s)
        keyframe_count = min(profile.keyframes, self.keyframes)
        frame_paths: list[str] = []
        frame_notes: list[dict[str, Any]] = []

        for index, scene_prompt in enumerate(
                self._scene_prompts(prompt, profile.name, keyframe_count), 1):
            result = self.image_module.generate(scene_prompt)
            path = self._artifact_path(result)
            frame_notes.append(
                {
                    "index": index,
                    "ok": bool(result.get("ok")),
                    "generator": str(result.get("generator") or ""),
                    "path": path,
                    "quality_class": str(result.get("quality_class") or ""),
                }
            )
            if path:
                frame_paths.append(path)

        if not frame_paths:
            return {
                "ok": False,
                "reply": (
                    "動画生成ルートは起動しましたが、MP4化に必要なキーフレームを"
                    "1枚も生成できませんでした。"
                ),
                "confidence": 0.90,
                "video_pipeline": VIDEO_VERSION,
                "frame_attempts": frame_notes,
            }

        if len(frame_paths) == 1:
            # A single valid frame is still enough for a real animated MP4
            # because Android applies motion/zoom while encoding.
            quality_note = "1枚のキーフレームからパン/ズーム動画を構成します。"
        else:
            quality_note = f"{len(frame_paths)}枚のキーフレームを補間して動画化します。"

        return {
            "ok": True,
            "reply": (
                "FMGの画像生成系から動画キーフレームを作成しました。"
                "Android側でH.264 MP4へエンコードします。\n"
                + quality_note
                + "\nこれは現段階では temporal diffusion ではなく、"
                "FMGキーフレーム＋端末エンコーダ方式です。"
            ),
            "confidence": 0.95,
            "video_pipeline": VIDEO_VERSION,
            "video_profile": {
                "duration_seconds": duration,
                "fps": profile.fps,
                "width": profile.width,
                "height": profile.height,
                "quality": profile.name,
                "keyframes": keyframe_count,
                "codec": "video/avc",
            },
            "frame_attempts": frame_notes,
            "memory_release": release_transient_memory(),
            "artifacts": [
                {
                    "type": "video_storyboard",
                    "name": "fap_fmg_storyboard",
                    "frames": frame_paths,
                    "duration_seconds": duration,
                    "fps": profile.fps,
                    "width": profile.width,
                    "height": profile.height,
                    "quality": profile.name,
                    "keyframes": keyframe_count,
                }
            ],
        }
