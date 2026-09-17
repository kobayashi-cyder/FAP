import unittest
from fap_media.audio_output import AudioOutputSkill, TTSRequest
from fap_media.contracts import MediaArtifact

class TTS:
    def synthesize(self, text, *, sample_rate_hz, voice):
        return MediaArtifact("audio", "audio/wav", b"RIFFx")

class TestAudioOutput(unittest.TestCase):
    def test_missing_provider_is_explicit(self):
        self.assertEqual(AudioOutputSkill().run(TTSRequest("hi")).status,"needs_provider")

    def test_tts_artifact(self):
        self.assertEqual(AudioOutputSkill(TTS()).run(TTSRequest("hi")).status,"ok")

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            TTSRequest(" ").validate()

if __name__=="__main__": unittest.main()
