from __future__ import annotations

import base64
import binascii
from typing import Any, Mapping

from fap_interaction.contracts import MediaArtifact
from fap_interaction.provider import ProviderExecutionError

from .command_json import CommandJSONClient


def _decode_artifact(response: Mapping[str, Any], *, expected_kind: str) -> MediaArtifact:
    kind = response.get("kind")
    mime_type = response.get("mime_type")
    payload = response.get("data_base64")
    metadata = response.get("metadata", {})
    if kind != expected_kind:
        raise ProviderExecutionError("provider artifact kind mismatch")
    if not isinstance(mime_type, str) or "/" not in mime_type:
        raise ProviderExecutionError("provider artifact MIME is invalid")
    if not isinstance(payload, str):
        raise ProviderExecutionError("provider artifact payload is missing")
    if not isinstance(metadata, dict):
        raise ProviderExecutionError("provider artifact metadata must be an object")
    try:
        data = base64.b64decode(payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ProviderExecutionError("provider artifact base64 is invalid") from exc
    return MediaArtifact(kind=kind, mime_type=mime_type, data=data, metadata=dict(metadata))


class CommandImageProvider:
    def __init__(self, client: CommandJSONClient):
        self.client = client

    def generate_image(self, request: Mapping[str, Any]) -> MediaArtifact:
        response = self.client.request({"op": "image", "request": dict(request)})
        return _decode_artifact(response, expected_kind="image")


class CommandSpeechToTextProvider:
    def __init__(self, client: CommandJSONClient):
        self.client = client

    def transcribe(self, pcm16: bytes, *, sample_rate_hz: int, channels: int) -> str:
        response = self.client.request(
            {
                "op": "stt",
                "pcm16_base64": base64.b64encode(bytes(pcm16)).decode("ascii"),
                "sample_rate_hz": int(sample_rate_hz),
                "channels": int(channels),
            }
        )
        text = response.get("text")
        if not isinstance(text, str):
            raise ProviderExecutionError("speech provider response is missing text")
        return text


class CommandTextToSpeechProvider:
    def __init__(self, client: CommandJSONClient):
        self.client = client

    def synthesize(self, text: str, *, sample_rate_hz: int, voice: str) -> MediaArtifact:
        response = self.client.request(
            {
                "op": "tts",
                "text": str(text),
                "sample_rate_hz": int(sample_rate_hz),
                "voice": str(voice),
            }
        )
        return _decode_artifact(response, expected_kind="audio")
