from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
V69 = ROOT.parents[1] / "v69" / "interaction"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V69))

from fap_interaction.audio_input import AudioInputSkill, PCM16Input
from fap_interaction.audio_output import AudioOutputSkill, TTSRequest
from fap_interaction.image_skill import ImageGenerationSkill, ImageRequest
from fap_interaction.provider import ProviderExecutionError, ProviderTimeoutError
from fap_interaction.voice_session import VoiceConversationSkill
from fap_provider_adapters.command_json import CommandJSONClient, ProcessProviderSpec
from fap_provider_adapters.providers import (
    CommandImageProvider,
    CommandSpeechToTextProvider,
    CommandTextToSpeechProvider,
)


FIXTURE = (Path(__file__).parent / "fixtures" / "provider_fixture.py").resolve()
PYTHON = Path(sys.executable).resolve()


def client(mode="ok", *, timeout_s=1.0, max_input_bytes=2 * 1024 * 1024,
           max_output_bytes=16 * 1024 * 1024):
    return CommandJSONClient(
        ProcessProviderSpec(
            executable=str(PYTHON),
            fixed_args=(str(FIXTURE), mode),
            timeout_s=timeout_s,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
        )
    )


class ProviderAdapterTests(unittest.TestCase):
    def test_requires_absolute_existing_executable(self):
        with self.assertRaises(ValueError):
            ProcessProviderSpec("python").validate()
        with self.assertRaises(ValueError):
            ProcessProviderSpec(str((ROOT / "missing-provider").resolve())).validate()

    def test_image_adapter_integrates_with_v69_skill(self):
        skill = ImageGenerationSkill(CommandImageProvider(client()))
        first = skill.run(ImageRequest("a blue sphere"))
        second = skill.run(ImageRequest("a blue sphere"))
        self.assertEqual(first.status, "ok")
        self.assertEqual(first.artifact.mime_type, "image/png")
        self.assertEqual(first.metadata["digest"], second.metadata["digest"])

    def test_stt_adapter_integrates_with_v69_skill(self):
        skill = AudioInputSkill(CommandSpeechToTextProvider(client()))
        result = skill.transcribe(PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["text"], "こんにちは")
        self.assertNotIn("data", result.metadata)
        self.assertNotIn("pcm16", result.metadata)

    def test_tts_adapter_integrates_with_v69_skill(self):
        skill = AudioOutputSkill(CommandTextToSpeechProvider(client()))
        result = skill.run(TTSRequest("こんにちは"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.artifact.mime_type, "audio/wav")
        self.assertEqual(len(result.metadata["digest"]), 64)

    def test_half_duplex_voice_with_command_adapters(self):
        audio_in = AudioInputSkill(CommandSpeechToTextProvider(client()))
        audio_out = AudioOutputSkill(CommandTextToSpeechProvider(client()))
        voice = VoiceConversationSkill(audio_in, audio_out, lambda text: text + "。応答")
        result = voice.run_turn(PCM16Input(b"\x00\x00\x10\x00"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["transcript"], "こんにちは")
        self.assertEqual(result.metadata["response_text"], "こんにちは。応答")

    def test_timeout_is_fail_closed(self):
        with self.assertRaises(ProviderTimeoutError):
            client("sleep", timeout_s=0.05).request({"op": "stt"})

    def test_nonzero_exit_is_fail_closed_without_stderr_leak(self):
        with self.assertRaisesRegex(ProviderExecutionError, "code 7"):
            client("error").request({"op": "stt"})

    def test_malformed_json_is_rejected(self):
        with self.assertRaisesRegex(ProviderExecutionError, "malformed JSON"):
            client("badjson").request({"op": "stt"})

    def test_output_limit_is_enforced(self):
        with self.assertRaisesRegex(ProviderExecutionError, "output limit"):
            client("oversize", max_output_bytes=1024).request({"op": "stt"})

    def test_input_limit_is_enforced_before_process_launch(self):
        tiny = client(max_input_bytes=1024)
        with self.assertRaisesRegex(ProviderExecutionError, "input limit"):
            CommandSpeechToTextProvider(tiny).transcribe(
                b"\x00\x00" * 2048, sample_rate_hz=16000, channels=1
            )

    def test_provider_environment_does_not_inherit_arbitrary_secret(self):
        old = os.environ.get("FAP_TEST_SECRET")
        os.environ["FAP_TEST_SECRET"] = "do-not-forward"
        try:
            result = client("env").request({"op": "probe"})
        finally:
            if old is None:
                os.environ.pop("FAP_TEST_SECRET", None)
            else:
                os.environ["FAP_TEST_SECRET"] = old
        self.assertFalse(result["secret_seen"])

    def test_bad_artifact_schema_is_rejected(self):
        provider = CommandImageProvider(client("badartifact"))
        with self.assertRaises(ProviderExecutionError):
            provider.generate_image({"prompt": "x"})


if __name__ == "__main__":
    unittest.main()
