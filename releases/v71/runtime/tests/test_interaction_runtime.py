from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
V69 = ROOT.parents[1] / "v69" / "interaction"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V69))

from fap_interaction.audio_input import PCM16Input
from fap_interaction.audio_output import TTSRequest
from fap_interaction.contracts import MediaArtifact
from fap_interaction.image_skill import ImageRequest
from fap_runtime import InteractionRuntime


class ImageProvider:
    def generate_image(self, request):
        return MediaArtifact("image", "image/png", b"PNG")


class STTProvider:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        return "音声入力"


class TTSProvider:
    def synthesize(self, text, *, sample_rate_hz, voice):
        return MediaArtifact("audio", "audio/wav", b"WAV")


class InteractionRuntimeTests(unittest.TestCase):
    def test_capabilities_do_not_claim_unconfigured_providers(self):
        runtime = InteractionRuntime(lambda text: "返答:" + text)
        caps = runtime.capabilities()
        self.assertTrue(caps.chat)
        self.assertFalse(caps.image_provider_configured)
        self.assertFalse(caps.stt_provider_configured)
        self.assertFalse(caps.tts_provider_configured)
        self.assertFalse(caps.half_duplex_voice_configured)

    def test_chat_works_without_media_providers(self):
        runtime = InteractionRuntime(lambda text: "返答:" + text)
        result = runtime.chat("こんにちは")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.kind, "chat")
        self.assertEqual(result.text, "返答:こんにちは")
        self.assertEqual(result.metadata["mode"], "rich")

    def test_chat_mode_command_is_preserved(self):
        runtime = InteractionRuntime(lambda text: "返答:" + text)
        result = runtime.chat(":brief")
        self.assertEqual(result.text, "mode=brief")
        self.assertEqual(runtime.capabilities().chat, True)

    def test_image_without_provider_is_needs_provider(self):
        runtime = InteractionRuntime(lambda text: text)
        result = runtime.image(ImageRequest("bird"))
        self.assertEqual(result.status, "needs_provider")

    def test_image_with_provider_passes_artifact(self):
        runtime = InteractionRuntime(lambda text: text, image_provider=ImageProvider())
        result = runtime.image(ImageRequest("bird"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.decision.artifact.mime_type, "image/png")

    def test_stt_without_provider_is_needs_provider_and_no_raw_pcm_metadata(self):
        runtime = InteractionRuntime(lambda text: text)
        audio = PCM16Input(b"\x00\x00\x10\x00")
        result = runtime.transcribe(audio)
        self.assertEqual(result.status, "needs_provider")
        self.assertNotIn("data", result.metadata)
        self.assertNotIn("pcm16", result.metadata)

    def test_stt_with_provider_returns_text(self):
        runtime = InteractionRuntime(lambda text: text, stt_provider=STTProvider())
        result = runtime.transcribe(PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.text, "音声入力")

    def test_tts_without_provider_is_needs_provider(self):
        runtime = InteractionRuntime(lambda text: text)
        result = runtime.speak(TTSRequest("hello"))
        self.assertEqual(result.status, "needs_provider")

    def test_voice_reports_exact_missing_providers(self):
        audio = PCM16Input(b"\x00\x00\x10\x00")
        runtime = InteractionRuntime(lambda text: text)
        self.assertEqual(runtime.voice_turn(audio).metadata["missing"], ("stt", "tts"))

        runtime = InteractionRuntime(lambda text: text, stt_provider=STTProvider())
        self.assertEqual(runtime.voice_turn(audio).metadata["missing"], ("tts",))

    def test_voice_half_duplex_success_when_both_configured(self):
        runtime = InteractionRuntime(
            lambda text: text + "!",
            stt_provider=STTProvider(),
            tts_provider=TTSProvider(),
        )
        self.assertTrue(runtime.capabilities().half_duplex_voice_configured)
        result = runtime.voice_turn(PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.text, "音声入力!")
        self.assertTrue(result.metadata["half_duplex"])


if __name__ == "__main__":
    unittest.main()
