from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
from .contracts import SkillDecision, SUPPORTED_IMAGE_FORMATS
from .provider import ImageProvider

@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    width: int = 1024
    height: int = 1024
    format: str = "png"
    seed: Optional[int] = None

    def validate(self) -> "ImageRequest":
        if not self.prompt.strip():
            raise ValueError("prompt is required")
        if not (64 <= self.width <= 4096 and 64 <= self.height <= 4096):
            raise ValueError("width/height out of range")
        if self.format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError("unsupported image format")
        return self

class ImageGenerationSkill:
    """Validated image request -> provider -> verified image artifact."""
    def __init__(self, provider: Optional[ImageProvider] = None):
        self.provider = provider

    def plan(self, request: ImageRequest) -> SkillDecision:
        request.validate()
        return SkillDecision("ok", "validated image generation plan",
                             metadata={"request": asdict(request), "requires_provider": self.provider is None})

    def run(self, request: ImageRequest) -> SkillDecision:
        request.validate()
        if self.provider is None:
            return SkillDecision("needs_provider", "no image renderer/provider configured",
                                 metadata={"request": asdict(request)})
        artifact = self.provider.generate_image(asdict(request)).require_nonempty()
        if not artifact.mime_type.startswith("image/"):
            raise ValueError("image provider returned non-image artifact")
        return SkillDecision("ok", "image generated", artifact=artifact, metadata={"digest": artifact.digest})
