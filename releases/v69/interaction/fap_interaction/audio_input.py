from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from .contracts import SkillDecision
from .provider import ProviderExecutionError, ProviderTimeoutError, SpeechToTextProvider


SUPPORTED_RATES = {8000, 16000, 24000, 32000, 44100, 48000}


@dataclass(frozen=True)
class PCM16Input:
    data: bytes
    sample_rate_hz: int = 16000
    channels: int = 1

    def validate(self) -> "PCM16Input":
        if not isinstance(self.data, (bytes, bytearray)) or not self.data or len(self.data) % 2:
            raise ValueError("PCM16 data must be non-empty and 16-bit aligned")
        if self.sample_rate_hz not in SUPPORTED_RATES:
            raise ValueError("unsupported sample rate")
        if self.channels not in {1, 2}:
            raise ValueError("channels must be 1 or 2")
        return self

    def rms(self) -> float:
        self.validate()
        samples = [int.from_bytes(self.data[i:i+2], "little", signed=True)
                   for i in range(0, len(self.data), 2)]
        return math.sqrt(sum(x*x for x in samples) / len(samples))


class AudioInputSkill:
    def __init__(self, stt: Optional[SpeechToTextProvider] = None, *, speech_rms_threshold: float = 250.0):
        self.stt = stt
        self.threshold = float(speech_rms_threshold)

    def inspect(self, audio: PCM16Input) -> SkillDecision:
        rms = audio.rms()
        return SkillDecision("ok", "audio inspected",
                             metadata={"rms": rms, "speech_likely": rms >= self.threshold})

    def transcribe(self, audio: PCM16Input) -> SkillDecision:
        audio.validate()
        inspection = self.inspect(audio).metadata
        if self.stt is None:
            return SkillDecision("needs_provider", "no speech-to-text provider configured",
                                 metadata=inspection)
        try:
            text = self.stt.transcribe(audio.data, sample_rate_hz=audio.sample_rate_hz,
                                       channels=audio.channels).strip()
        except ProviderTimeoutError:
            return SkillDecision("rejected", "speech-to-text provider timeout", metadata=inspection)
        except ProviderExecutionError as exc:
            return SkillDecision("rejected", f"speech-to-text provider error: {exc}",
                                 metadata=inspection)
        if not text:
            raise ValueError("speech-to-text provider returned empty transcript")
        return SkillDecision("ok", "speech transcribed", metadata={"text": text, **inspection})
