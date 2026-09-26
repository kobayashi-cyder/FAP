from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from .contracts import SkillDecision
from .provider import ImageProvider, ProviderExecutionError, ProviderTimeoutError


SUPPORTED_IMAGE_FORMATS = {"png", "jpeg", "webp"}
MIME_BY_FORMAT = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


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
    def __init__(self, provider: Optional[ImageProvider] = None):
        self.provider = provider

    def run(self, request: ImageRequest) -> SkillDecision:
        request.validate()
        meta = {"request": asdict(request)}
        if self.provider is None:
            return SkillDecision("needs_provider", "no image provider configured", metadata=meta)
        try:
            artifact = self.provider.generate_image(asdict(request))
        except ProviderTimeoutError:
            return SkillDecision("rejected", "image provider timeout", metadata=meta)
        except ProviderExecutionError as exc:
            return SkillDecision("rejected", f"image provider error: {exc}", metadata=meta)

        artifact.require(kind="image", mime_prefix="image/")
        expected = MIME_BY_FORMAT[request.format]
        if artifact.mime_type != expected:
            raise ValueError(f"image MIME mismatch: expected {expected}")
        return SkillDecision("ok", "image generated", artifact=artifact,
                             metadata={**meta, "digest": artifact.digest})
