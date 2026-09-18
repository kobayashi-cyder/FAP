from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fap_interaction.provider import ProviderExecutionError, ProviderTimeoutError


_PROTOCOL_VERSION = 1
_ALLOWED = frozenset({"image", "stt", "tts"})


@dataclass(frozen=True)
class CapabilityProbeResult:
    status: str
    protocol_version: Optional[int] = None
    provider_id: Optional[str] = None
    capabilities: tuple[str, ...] = ()
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in {"healthy", "unavailable", "incompatible", "error"}:
            raise ValueError("invalid provider probe status")

    @property
    def ready(self) -> bool:
        return self.status == "healthy"


@dataclass(frozen=True)
class CapabilityGate:
    image: bool
    stt: bool
    tts: bool
    half_duplex_voice: bool

    @classmethod
    def from_probe(cls, result: CapabilityProbeResult) -> "CapabilityGate":
        caps = set(result.capabilities) if result.ready else set()
        return cls(
            image="image" in caps,
            stt="stt" in caps,
            tts="tts" in caps,
            half_duplex_voice={"stt", "tts"}.issubset(caps),
        )


class ProviderCapabilityProbe:
    """No-content capability handshake for a V70 CommandJSONClient-compatible provider."""

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _validate_provider_id(value) -> str:
        if not isinstance(value, str):
            raise ProviderExecutionError("probe provider_id must be a string")
        value = value.strip()
        if not value or len(value) > 128:
            raise ProviderExecutionError("probe provider_id is invalid")
        if any(ord(ch) < 32 for ch in value):
            raise ProviderExecutionError("probe provider_id contains control characters")
        return value

    @staticmethod
    def _validate_capabilities(value) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise ProviderExecutionError("probe capabilities must be a list")
        if any(not isinstance(item, str) for item in value):
            raise ProviderExecutionError("probe capability names must be strings")
        if len(value) != len(set(value)):
            raise ProviderExecutionError("probe capability list contains duplicates")
        unknown = set(value) - _ALLOWED
        if unknown:
            raise ProviderExecutionError("probe reported unknown capability")
        return tuple(sorted(value))

    def run(self) -> CapabilityProbeResult:
        try:
            response = self.client.request(
                {"op": "probe", "protocol_version": _PROTOCOL_VERSION}
            )
        except ProviderTimeoutError:
            return CapabilityProbeResult(
                status="unavailable",
                reason="provider_probe_timeout",
            )
        except ProviderExecutionError:
            return CapabilityProbeResult(
                status="error",
                reason="provider_probe_error",
            )

        version = response.get("protocol_version")
        if version != _PROTOCOL_VERSION:
            return CapabilityProbeResult(
                status="incompatible",
                protocol_version=version if isinstance(version, int) else None,
                reason="protocol_version_mismatch",
            )

        try:
            provider_id = self._validate_provider_id(response.get("provider_id"))
            capabilities = self._validate_capabilities(response.get("capabilities"))
        except ProviderExecutionError:
            return CapabilityProbeResult(
                status="error",
                protocol_version=version,
                reason="invalid_probe_response",
            )

        if response.get("ready") is not True:
            return CapabilityProbeResult(
                status="unavailable",
                protocol_version=version,
                provider_id=provider_id,
                capabilities=capabilities,
                reason="provider_not_ready",
            )

        return CapabilityProbeResult(
            status="healthy",
            protocol_version=version,
            provider_id=provider_id,
            capabilities=capabilities,
        )
