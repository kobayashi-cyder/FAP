from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Optional

from fap_interaction.audio_input import AudioInputSkill, PCM16Input
from fap_interaction.audio_output import AudioOutputSkill, TTSRequest
from fap_interaction.chat import ChatSession
from fap_interaction.contracts import SkillDecision
from fap_interaction.image_skill import ImageGenerationSkill, ImageRequest
from fap_interaction.provider import ImageProvider, SpeechToTextProvider, TextToSpeechProvider
from fap_interaction.voice_session import VoiceConversationSkill


@dataclass(frozen=True)
class RuntimeCapabilities:
    chat: bool = True
    image_provider_configured: bool = False
    stt_provider_configured: bool = False
    tts_provider_configured: bool = False
    half_duplex_voice_configured: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeResult:
    status: str
    kind: str
    text: Optional[str] = None
    decision: Optional[SkillDecision] = None
    metadata: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.status not in {"ok", "needs_provider", "rejected"}:
            raise ValueError("invalid runtime status")


class InteractionRuntime:
    """Small runtime router for the V69/V70 interaction stack.

    Provider presence means configured, not proven healthy. Real capability claims still
    require independently exercised concrete providers.
    """

    def __init__(
        self,
        responder: Callable[[str], str],
        *,
        chat_responder: Optional[Callable[[str, str, str], str]] = None,
        image_provider: Optional[ImageProvider] = None,
        stt_provider: Optional[SpeechToTextProvider] = None,
        tts_provider: Optional[TextToSpeechProvider] = None,
        chat_mode: str = "rich",
        max_chat_turns: int = 24,
    ):
        self.responder = responder
        self.chat_responder = chat_responder
        self.image_skill = ImageGenerationSkill(image_provider)
        self.audio_in = AudioInputSkill(stt_provider)
        self.audio_out = AudioOutputSkill(tts_provider)
        self.chat_session = ChatSession(mode=chat_mode, max_turns=max_chat_turns)
        self.voice = VoiceConversationSkill(self.audio_in, self.audio_out, responder)
        self._image_provider = image_provider
        self._stt_provider = stt_provider
        self._tts_provider = tts_provider

    def capabilities(self) -> RuntimeCapabilities:
        stt = self._stt_provider is not None
        tts = self._tts_provider is not None
        return RuntimeCapabilities(
            chat=True,
            image_provider_configured=self._image_provider is not None,
            stt_provider_configured=stt,
            tts_provider_configured=tts,
            half_duplex_voice_configured=stt and tts,
        )

    def chat(self, text: str) -> RuntimeResult:
        responder = self.chat_responder
        if responder is None:
            def responder(user_text: str, _context: str, _mode: str) -> str:
                return self.responder(user_text)
        output = self.chat_session.submit(text, responder)
        return RuntimeResult(
            status="ok",
            kind="chat",
            text=output,
            metadata={"mode": self.chat_session.mode, "turns": len(self.chat_session.turns)},
        )

    def image(self, request: ImageRequest) -> RuntimeResult:
        decision = self.image_skill.run(request)
        return RuntimeResult(
            status=decision.status,
            kind="image",
            decision=decision,
            metadata={"provider_configured": self._image_provider is not None},
        )

    def transcribe(self, audio: PCM16Input) -> RuntimeResult:
        decision = self.audio_in.transcribe(audio)
        text = decision.metadata.get("text") if decision.metadata else None
        safe_meta = dict(decision.metadata)
        safe_meta.pop("text", None)
        return RuntimeResult(
            status=decision.status,
            kind="stt",
            text=text,
            decision=decision,
            metadata={"provider_configured": self._stt_provider is not None, **safe_meta},
        )

    def speak(self, request: TTSRequest) -> RuntimeResult:
        decision = self.audio_out.run(request)
        return RuntimeResult(
            status=decision.status,
            kind="tts",
            decision=decision,
            metadata={"provider_configured": self._tts_provider is not None},
        )

    def voice_turn(self, audio: PCM16Input, *, voice: str = "default") -> RuntimeResult:
        missing = []
        if self._stt_provider is None:
            missing.append("stt")
        if self._tts_provider is None:
            missing.append("tts")
        if missing:
            return RuntimeResult(
                status="needs_provider",
                kind="voice",
                metadata={"missing": tuple(missing), "half_duplex": True},
            )
        decision = self.voice.run_turn(audio, voice=voice)
        safe_meta = dict(decision.metadata)
        safe_meta["half_duplex"] = True
        return RuntimeResult(
            status=decision.status,
            kind="voice",
            decision=decision,
            text=safe_meta.get("response_text"),
            metadata=safe_meta,
        )
