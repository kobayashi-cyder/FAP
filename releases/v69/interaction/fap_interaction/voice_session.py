from __future__ import annotations

from typing import Callable

from .audio_input import AudioInputSkill, PCM16Input
from .audio_output import AudioOutputSkill, TTSRequest
from .contracts import SkillDecision


class VoiceConversationSkill:
    """Half-duplex baseline: PCM16 -> STT -> responder -> TTS.

    Full duplex, barge-in, echo cancellation, streaming and wake-word behavior
    are intentionally outside this baseline until separately verified.
    """

    def __init__(self, audio_in: AudioInputSkill, audio_out: AudioOutputSkill,
                 responder: Callable[[str], str]):
        self.audio_in = audio_in
        self.audio_out = audio_out
        self.responder = responder

    def run_turn(self, audio: PCM16Input, *, voice: str = "default") -> SkillDecision:
        stt = self.audio_in.transcribe(audio)
        if stt.status != "ok":
            return stt
        transcript = str(stt.metadata["text"])
        response = str(self.responder(transcript)).strip()
        if not response:
            raise ValueError("responder returned empty text")

        tts = self.audio_out.run(TTSRequest(response, voice=voice))
        if tts.status != "ok":
            return SkillDecision(tts.status, tts.reason,
                                 metadata={"transcript": transcript,
                                           "response_text": response, **tts.metadata})
        return SkillDecision("ok", "voice turn completed", artifact=tts.artifact,
                             metadata={"transcript": transcript,
                                       "response_text": response,
                                       "audio_digest": tts.artifact.digest})
