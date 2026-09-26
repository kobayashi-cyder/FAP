from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
V73 = ROOT.parents[1] / "v73" / "provider_probe"
V71 = ROOT.parents[1] / "v71" / "runtime"
V69 = ROOT.parents[1] / "v69" / "interaction"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V73))
sys.path.insert(0, str(V71))
sys.path.insert(0, str(V69))

from fap_gated_runtime import GatedInteractionRuntime
from fap_interaction.audio_input import PCM16Input
from fap_interaction.audio_output import TTSRequest
from fap_interaction.contracts import MediaArtifact
from fap_interaction.image_skill import ImageRequest
from fap_provider_probe import CapabilityProbeResult
from fap_runtime import InteractionRuntime


class SpyImage:
    def __init__(self):
        self.calls = 0
    def generate_image(self, request):
        self.calls += 1
        return MediaArtifact("image", "image/png", b"PNG")


class SpySTT:
    def __init__(self):
        self.calls = 0
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        self.calls += 1
        return "音声"


class SpyTTS:
    def __init__(self):
        self.calls = 0
    def synthesize(self, text, *, sample_rate_hz, voice):
        self.calls += 1
        return MediaArtifact("audio", "audio/wav", b"WAV")


def healthy(*caps):
    return CapabilityProbeResult(
        status="healthy",
        protocol_version=1,
        provider_id="fixture",
        capabilities=tuple(sorted(caps)),
    )


class GatedRuntimeTests(unittest.TestCase):
    def make_runtime(self):
        image, stt, tts = SpyImage(), SpySTT(), SpyTTS()
        runtime = InteractionRuntime(
            lambda text: "返答:" + text,
            image_provider=image,
            stt_provider=stt,
            tts_provider=tts,
        )
        return GatedInteractionRuntime(runtime), image, stt, tts

    def test_chat_is_independent_of_media_probe(self):
        gated, image, stt, tts = self.make_runtime()
        result = gated.chat("こんにちは")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.text, "返答:こんにちは")
        self.assertEqual((image.calls, stt.calls, tts.calls), (0, 0, 0))

    def test_media_is_blocked_before_probe_without_invocation(self):
        gated, image, stt, tts = self.make_runtime()
        r = gated.image(ImageRequest("bird"))
        self.assertEqual(r.status, "rejected")
        self.assertEqual(r.metadata["reason"], "provider_probe_required")
        self.assertEqual(image.calls, 0)

    def test_unhealthy_probe_blocks_provider_invocation(self):
        gated, image, stt, tts = self.make_runtime()
        gated.update_probe(CapabilityProbeResult(status="unavailable", reason="provider_not_ready"))
        self.assertEqual(gated.transcribe(PCM16Input(b"\x00\x00")).status, "rejected")
        self.assertEqual(stt.calls, 0)

    def test_undeclared_capability_is_blocked(self):
        gated, image, stt, tts = self.make_runtime()
        gated.update_probe(healthy("stt", "tts"))
        result = gated.image(ImageRequest("bird"))
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.metadata["reason"], "capability_not_declared")
        self.assertEqual(image.calls, 0)

    def test_healthy_image_capability_invokes_provider(self):
        gated, image, stt, tts = self.make_runtime()
        gated.update_probe(healthy("image"))
        result = gated.image(ImageRequest("bird"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(image.calls, 1)

    def test_voice_requires_both_stt_and_tts_capabilities(self):
        gated, image, stt, tts = self.make_runtime()
        gated.update_probe(healthy("stt"))
        blocked = gated.voice_turn(PCM16Input(b"\x00\x00"))
        self.assertEqual(blocked.status, "rejected")
        self.assertEqual((stt.calls, tts.calls), (0, 0))

        gated.update_probe(healthy("stt", "tts"))
        ok = gated.voice_turn(PCM16Input(b"\x00\x00"))
        self.assertEqual(ok.status, "ok")
        self.assertEqual((stt.calls, tts.calls), (1, 1))

    def test_unconfigured_provider_is_needs_provider_even_with_healthy_probe(self):
        runtime = InteractionRuntime(lambda text: text)
        gated = GatedInteractionRuntime(runtime, healthy("image", "stt", "tts"))
        result = gated.image(ImageRequest("bird"))
        self.assertEqual(result.status, "needs_provider")
        self.assertEqual(result.metadata["reason"], "provider_not_configured")

    def test_status_requires_both_configuration_and_probe(self):
        gated, image, stt, tts = self.make_runtime()
        before = gated.status()
        self.assertFalse(before.image_ready)
        self.assertEqual(before.probe_status, "not_probed")
        after = gated.update_probe(healthy("image", "stt", "tts"))
        self.assertTrue(after.image_ready)
        self.assertTrue(after.stt_ready)
        self.assertTrue(after.tts_ready)
        self.assertTrue(after.half_duplex_voice_ready)


if __name__ == "__main__":
    unittest.main()
