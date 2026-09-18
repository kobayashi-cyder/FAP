import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_interaction.audio_input import AudioInputSkill, PCM16Input
from fap_interaction.audio_output import AudioOutputSkill, TTSRequest
from fap_interaction.chat import ChatSession
from fap_interaction.contracts import MediaArtifact
from fap_interaction.image_skill import ImageGenerationSkill, ImageRequest
from fap_interaction.provider import ProviderExecutionError, ProviderTimeoutError
from fap_interaction.voice_session import VoiceConversationSkill


class ImageOK:
    def generate_image(self, request):
        return MediaArtifact("image", "image/png", b"PNGDATA", {"provider": "fixture"})


class ImageWrongMime:
    def generate_image(self, request):
        return MediaArtifact("image", "audio/wav", b"x")


class ImageEmpty:
    def generate_image(self, request):
        return MediaArtifact("image", "image/png", b"")


class ImageTimeout:
    def generate_image(self, request):
        raise ProviderTimeoutError()


class ImageError:
    def generate_image(self, request):
        raise ProviderExecutionError("fixture failure")


class STTOK:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        return "こんにちは"


class STTEmpty:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        return "  "


class STTTimeout:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        raise ProviderTimeoutError()


class STTError:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        raise ProviderExecutionError("fixture failure")


class TTSOK:
    def synthesize(self, text, *, sample_rate_hz, voice):
        return MediaArtifact("audio", "audio/wav", b"WAVDATA")


class TTSWrongMime:
    def synthesize(self, text, *, sample_rate_hz, voice):
        return MediaArtifact("audio", "image/png", b"x")


class TTSEmpty:
    def synthesize(self, text, *, sample_rate_hz, voice):
        return MediaArtifact("audio", "audio/wav", b"")


class TTSError:
    def synthesize(self, text, *, sample_rate_hz, voice):
        raise ProviderExecutionError("fixture failure")


class InteractionTests(unittest.TestCase):
    def test_chat_modes_and_bounded_context(self):
        session = ChatSession(max_turns=4)
        self.assertEqual(session.submit(":brief", lambda *_: "unused"), "mode=brief")
        self.assertEqual(session.mode, "brief")
        seen = []
        def responder(text, context, mode):
            seen.append((text, context, mode))
            return "ok:" + text
        session.submit("一", responder)
        session.submit("二", responder)
        session.submit("三", responder)
        self.assertEqual(len(session.turns), 4)
        self.assertEqual(seen[-1][2], "brief")
        self.assertIn("user: 二", seen[-1][1])

    def test_chat_rejects_empty_input_and_response(self):
        with self.assertRaises(ValueError):
            ChatSession().submit("   ", lambda *_: "unused")
        with self.assertRaises(ValueError):
            ChatSession().submit("test", lambda *_: "")

    def test_image_missing_provider(self):
        self.assertEqual(ImageGenerationSkill().run(ImageRequest("cat")).status, "needs_provider")

    def test_image_success_and_digest(self):
        result = ImageGenerationSkill(ImageOK()).run(ImageRequest("cat"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.metadata["digest"]), 64)

    def test_image_wrong_mime_and_empty_rejected(self):
        with self.assertRaises(ValueError):
            ImageGenerationSkill(ImageWrongMime()).run(ImageRequest("cat"))
        with self.assertRaises(ValueError):
            ImageGenerationSkill(ImageEmpty()).run(ImageRequest("cat"))

    def test_image_timeout_and_provider_error_are_rejected(self):
        self.assertEqual(ImageGenerationSkill(ImageTimeout()).run(ImageRequest("cat")).status,
                         "rejected")
        self.assertEqual(ImageGenerationSkill(ImageError()).run(ImageRequest("cat")).status,
                         "rejected")

    def test_pcm_validation_and_inspection(self):
        with self.assertRaises(ValueError):
            PCM16Input(b"x").validate()
        result = AudioInputSkill().inspect(PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertNotIn("data", result.metadata)

    def test_stt_missing_empty_timeout_and_success(self):
        audio = PCM16Input(b"\x00\x00\x10\x00")
        self.assertEqual(AudioInputSkill().transcribe(audio).status, "needs_provider")
        with self.assertRaises(ValueError):
            AudioInputSkill(STTEmpty()).transcribe(audio)
        self.assertEqual(AudioInputSkill(STTTimeout()).transcribe(audio).status, "rejected")
        self.assertEqual(AudioInputSkill(STTError()).transcribe(audio).status, "rejected")
        self.assertEqual(AudioInputSkill(STTOK()).transcribe(audio).metadata["text"], "こんにちは")

    def test_tts_missing_wrong_mime_error_and_success(self):
        req = TTSRequest("hello")
        self.assertEqual(AudioOutputSkill().run(req).status, "needs_provider")
        with self.assertRaises(ValueError):
            AudioOutputSkill(TTSWrongMime()).run(req)
        with self.assertRaises(ValueError):
            AudioOutputSkill(TTSEmpty()).run(req)
        self.assertEqual(AudioOutputSkill(TTSError()).run(req).status, "rejected")
        self.assertEqual(AudioOutputSkill(TTSOK()).run(req).status, "ok")

    def test_voice_half_duplex_success(self):
        audio_in = AudioInputSkill(STTOK())
        audio_out = AudioOutputSkill(TTSOK())
        result = VoiceConversationSkill(audio_in, audio_out, lambda t: t + "！").run_turn(
            PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["transcript"], "こんにちは")
        self.assertEqual(result.metadata["response_text"], "こんにちは！")

    def test_voice_propagates_missing_provider(self):
        result = VoiceConversationSkill(AudioInputSkill(), AudioOutputSkill(TTSOK()),
                                        lambda t: t).run_turn(PCM16Input(b"\x00\x00"))
        self.assertEqual(result.status, "needs_provider")


if __name__ == "__main__":
    unittest.main()
