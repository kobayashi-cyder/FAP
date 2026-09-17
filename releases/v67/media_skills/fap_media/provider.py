from __future__ import annotations
from typing import Protocol, Any, Mapping
from .contracts import MediaArtifact

class ImageProvider(Protocol):
    def generate_image(self, request: Mapping[str, Any]) -> MediaArtifact: ...

class VideoProvider(Protocol):
    def render_video(self, request: Mapping[str, Any]) -> MediaArtifact: ...

class SpeechToTextProvider(Protocol):
    def transcribe(self, pcm16: bytes, *, sample_rate_hz: int, channels: int) -> str: ...

class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, *, sample_rate_hz: int, voice: str) -> MediaArtifact: ...

class MissingProviderError(RuntimeError):
    pass
