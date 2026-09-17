from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .contracts import SkillDecision
from .provider import TextToSpeechProvider

@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str = "default"
    sample_rate_hz: int = 24000
    def validate(self):
        if not self.text.strip(): raise ValueError("text is required")
        if len(self.text) > 20000: raise ValueError("text too long for one synthesis request")
        if self.sample_rate_hz not in {16000,22050,24000,32000,44100,48000}: raise ValueError("unsupported sample rate")
        if not self.voice.strip(): raise ValueError("voice is required")
        return self

class AudioOutputSkill:
    def __init__(self, tts: Optional[TextToSpeechProvider]=None): self.tts=tts
    def run(self,request:TTSRequest)->SkillDecision:
        request.validate()
        if self.tts is None:
            return SkillDecision("needs_provider","no text-to-speech provider configured",metadata={"text_chars":len(request.text),"voice":request.voice,"sample_rate_hz":request.sample_rate_hz})
        artifact=self.tts.synthesize(request.text,sample_rate_hz=request.sample_rate_hz,voice=request.voice).require_nonempty()
        if not artifact.mime_type.startswith("audio/"): raise ValueError("text-to-speech provider returned non-audio artifact")
        return SkillDecision("ok","speech synthesized",artifact=artifact,metadata={"digest":artifact.digest})
