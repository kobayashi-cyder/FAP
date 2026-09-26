from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fap_interaction.audio_input import PCM16Input
from fap_interaction.audio_output import TTSRequest
from fap_interaction.image_skill import ImageRequest
from fap_runtime import InteractionRuntime, RuntimeResult
from fap_provider_probe import CapabilityGate, CapabilityProbeResult


@dataclass(frozen=True)
class GatedRuntimeStatus:
    chat: bool
    image_ready: bool
    stt_ready: bool
    tts_ready: bool
    half_duplex_voice_ready: bool
    probe_status: str
    probe_reason: Optional[str]
    provider_id: Optional[str]


class GatedInteractionRuntime:
    """Interaction runtime that refuses media calls until the provider probe allows them."""

    def __init__(self, runtime: InteractionRuntime, probe: Optional[CapabilityProbeResult] = None):
        self.runtime = runtime
        self.probe = probe

    def update_probe(self, result: CapabilityProbeResult) -> GatedRuntimeStatus:
        self.probe = result
        return self.status()

    def status(self) -> GatedRuntimeStatus:
        configured = self.runtime.capabilities()
        gate = CapabilityGate.from_probe(self.probe) if self.probe is not None else CapabilityGate(False, False, False, False)
        return GatedRuntimeStatus(
            chat=True,
            image_ready=configured.image_provider_configured and gate.image,
            stt_ready=configured.stt_provider_configured and gate.stt,
            tts_ready=configured.tts_provider_configured and gate.tts,
            half_duplex_voice_ready=configured.half_duplex_voice_configured and gate.half_duplex_voice,
            probe_status=self.probe.status if self.probe is not None else "not_probed",
            probe_reason=self.probe.reason if self.probe is not None else "provider_probe_required",
            provider_id=self.probe.provider_id if self.probe is not None else None,
        )

    def chat(self, text: str) -> RuntimeResult:
        return self.runtime.chat(text)

    def _blocked(self, kind: str, *, configured: bool, allowed: bool) -> Optional[RuntimeResult]:
        if not configured:
            return RuntimeResult(
                status="needs_provider",
                kind=kind,
                metadata={"reason": "provider_not_configured"},
            )
        if self.probe is None:
            return RuntimeResult(
                status="rejected",
                kind=kind,
                metadata={"reason": "provider_probe_required"},
            )
        if self.probe.status != "healthy":
            return RuntimeResult(
                status="rejected",
                kind=kind,
                metadata={
                    "reason": self.probe.reason or "provider_not_healthy",
                    "probe_status": self.probe.status,
                },
            )
        if not allowed:
            return RuntimeResult(
                status="rejected",
                kind=kind,
                metadata={"reason": "capability_not_declared"},
            )
        return None

    def image(self, request: ImageRequest) -> RuntimeResult:
        configured = self.runtime.capabilities().image_provider_configured
        gate = CapabilityGate.from_probe(self.probe) if self.probe is not None else CapabilityGate(False, False, False, False)
        blocked = self._blocked("image", configured=configured, allowed=gate.image)
        return blocked if blocked is not None else self.runtime.image(request)

    def transcribe(self, audio: PCM16Input) -> RuntimeResult:
        configured = self.runtime.capabilities().stt_provider_configured
        gate = CapabilityGate.from_probe(self.probe) if self.probe is not None else CapabilityGate(False, False, False, False)
        blocked = self._blocked("stt", configured=configured, allowed=gate.stt)
        return blocked if blocked is not None else self.runtime.transcribe(audio)

    def speak(self, request: TTSRequest) -> RuntimeResult:
        configured = self.runtime.capabilities().tts_provider_configured
        gate = CapabilityGate.from_probe(self.probe) if self.probe is not None else CapabilityGate(False, False, False, False)
        blocked = self._blocked("tts", configured=configured, allowed=gate.tts)
        return blocked if blocked is not None else self.runtime.speak(request)

    def voice_turn(self, audio: PCM16Input, *, voice: str = "default") -> RuntimeResult:
        configured = self.runtime.capabilities().half_duplex_voice_configured
        gate = CapabilityGate.from_probe(self.probe) if self.probe is not None else CapabilityGate(False, False, False, False)
        blocked = self._blocked("voice", configured=configured, allowed=gate.half_duplex_voice)
        return blocked if blocked is not None else self.runtime.voice_turn(audio, voice=voice)
