from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
from .contracts import SkillDecision, SUPPORTED_VIDEO_FORMATS
from .provider import VideoProvider

@dataclass(frozen=True)
class Scene:
    text: str
    duration_s: float
    def validate(self):
        if not self.text.strip(): raise ValueError("scene text is required")
        if not (0.1 <= self.duration_s <= 600): raise ValueError("scene duration out of range")
        return self

@dataclass(frozen=True)
class VideoRequest:
    scenes: Tuple[Scene, ...]
    width: int = 1920
    height: int = 1080
    fps: int = 30
    format: str = "mp4"
    def validate(self):
        if not self.scenes: raise ValueError("at least one scene is required")
        for scene in self.scenes: scene.validate()
        if not (1 <= self.fps <= 120): raise ValueError("fps out of range")
        if self.width <= 0 or self.height <= 0: raise ValueError("invalid dimensions")
        if self.format not in SUPPORTED_VIDEO_FORMATS: raise ValueError("unsupported video format")
        return self

class VideoGenerationSkill:
    """Deterministic storyboard/timing plan with optional renderer/provider."""
    def __init__(self, provider: Optional[VideoProvider] = None): self.provider = provider

    def render_plan(self, request: VideoRequest):
        request.validate(); frames=[]; cursor=0
        for index, scene in enumerate(request.scenes):
            count=max(1, round(scene.duration_s * request.fps))
            frames.append({"scene":index,"start_frame":cursor,"frame_count":count,"text":scene.text})
            cursor += count
        return {"schema":1,"width":request.width,"height":request.height,"fps":request.fps,
                "format":request.format,"total_frames":cursor,"scenes":frames}

    def run(self, request: VideoRequest) -> SkillDecision:
        plan=self.render_plan(request)
        if self.provider is None:
            return SkillDecision("needs_provider", "video plan ready; renderer/provider not configured", metadata={"render_plan":plan})
        artifact=self.provider.render_video({"request":asdict(request),"render_plan":plan}).require_nonempty()
        if not artifact.mime_type.startswith("video/"): raise ValueError("video provider returned non-video artifact")
        return SkillDecision("ok","video rendered",artifact=artifact,metadata={"render_plan":plan,"digest":artifact.digest})
