import unittest
from fap_media.audio_input import AudioInputSkill, PCM16Input

class STT:
    def transcribe(self, pcm16, *, sample_rate_hz, channels):
        return "hello"

class TestAudioInput(unittest.TestCase):
    def test_alignment(self):
        with self.assertRaises(ValueError):
            PCM16Input(b"x").validate()

    def test_transcribe(self):
        audio=PCM16Input((1000).to_bytes(2,"little",signed=True)*10)
        result=AudioInputSkill(STT()).transcribe(audio)
        self.assertEqual(result.metadata["text"],"hello")
        self.assertTrue(result.metadata["speech_likely"])

if __name__=="__main__": unittest.main()
