from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import SkillDecision
from .provider import ProviderExecutionError, ProviderTimeoutError, TextToSpeechProvider


SUPPORTED_RATES = {16000, 22050, 24000, 32000, 44100, 48000}


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str = "default"
    sample_rate_hz: int = 24000

    def validate(self) -> "TTSRequest":
        if not self.text.strip():
            raise ValueError("text is required")
        if len(self.text) > 20000:
            raise ValueError("text too long for one synthesis request")
        if self.sample_rate_hz not in SUPPORTED_RATES:
            raise ValueError("unsupported sample rate")
        if not self.voice.strip():
            raise ValueError("voice is required")
        return self


class AudioOutputSkill:
    def __init__(self, tts: Optional[TextToSpeechProvider] = None):
        self.tts = tts

    def run(self, request: TTSRequest) -> SkillDecision:
        request.validate()
        meta = {"text_chars": len(request.text), "voice": request.voice,
                "sample_rate_hz": request.sample_rate_hz}
        if self.tts is None:
            return SkillDecision("needs_provider", "no text-to-speech provider configured",
                                 metadata=meta)
        try:
            artifact = self.tts.synthesize(request.text, sample_rate_hz=request.sample_rate_hz,
                                           voice=request.voice)
        except ProviderTimeoutError:
            return SkillDecision("rejected", "text-to-speech provider timeout", metadata=meta)
        except ProviderExecutionError as exc:
            return SkillDecision("rejected", f"text-to-speech provider error: {exc}",
                                 metadata=meta)
        artifact.require(kind="audio", mime_prefix="audio/")
        return SkillDecision("ok", "speech synthesized", artifact=artifact,
                             metadata={**meta, "digest": artifact.digest})
