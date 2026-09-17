import unittest
from fap_media.audio_input import AudioInputSkill, PCM16Input
from fap_media.audio_output import AudioOutputSkill
from fap_media.voice_session import VoiceConversationSkill
from fap_media.contracts import MediaArtifact

class STT:
    def transcribe(self, pcm16, *, sample_rate_hz, channels): return "ping"
class TTS:
    def synthesize(self, text, *, sample_rate_hz, voice): return MediaArtifact("audio","audio/wav",text.encode())

class TestVoiceSession(unittest.TestCase):
    def test_turn(self):
        skill=VoiceConversationSkill(AudioInputSkill(STT()),AudioOutputSkill(TTS()),lambda _:"pong")
        audio=PCM16Input((1000).to_bytes(2,"little",signed=True)*10)
        result=skill.run_turn(audio)
        self.assertEqual(result.status,"ok")
        self.assertEqual(result.metadata["transcript"],"ping")
        self.assertEqual(result.metadata["response_text"],"pong")

if __name__=="__main__": unittest.main()
