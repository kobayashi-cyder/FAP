import os
from pathlib import Path
import stat
import tempfile
import unittest

from fap_speech import PCM16Audio, STTResult, TTSResult
from fap_speech_fluent import (
    FluentConversationRuntime,
    FluentSpeechConfig,
    LocalJSONSTTBackend,
    UtteranceDetection,
    detect_utterance,
    split_for_speech,
)


def samples(ms, value, rate=16000):
    return (int(value),) * int(rate * ms / 1000)


class FakeSTT:
    def __init__(self, text="こんにちは", confidence=0.9, state="ok"):
        self.result = STTResult(text, confidence, state)

    def transcribe_audio(self, audio):
        return self.result


class FakeTTS:
    sample_rate = 16000

    def __init__(self):
        self.texts = []

    def synthesize(self, text):
        self.texts.append(text)
        return TTSResult(PCM16Audio(self.sample_rate, (100,) * 100), "ok")


class FluentSpeechTests(unittest.TestCase):
    def test_detect_utterance_uses_adaptive_noise_and_trailing_silence(self):
        cfg = FluentSpeechConfig(
            calibration_ms=200,
            trailing_silence_ms=200,
            min_speech_ms=80,
            pre_roll_ms=40,
            absolute_rms_floor=100,
            noise_multiplier=2.5,
        )
        audio = PCM16Audio(
            16000,
            samples(300, 20) + samples(500, 1200) + samples(400, 10),
        )
        result = detect_utterance(audio, cfg)
        self.assertEqual(result.state, "ok")
        self.assertGreater(result.speech_ms, 300)
        self.assertLess(result.audio.duration_seconds, 1.0)
        self.assertGreater(result.threshold_rms, 0)

    def test_detect_utterance_rejects_silence(self):
        cfg = FluentSpeechConfig(calibration_ms=100, absolute_rms_floor=200)
        result = detect_utterance(
            PCM16Audio(16000, samples(1000, 10)),
            cfg,
        )
        self.assertEqual(result.state, "no_speech")
        self.assertEqual(result.audio.samples, ())

    def test_split_for_speech_returns_multiple_early_chunks(self):
        text = "最初の文です。次の文です。さらに詳しく説明しますが、長すぎる部分は分割します。"
        chunks = split_for_speech(text, max_chars=18)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(0 < len(c) <= 18 for c in chunks))

    def test_turn_transcribes_calls_handler_and_speaks_by_chunk(self):
        cfg = FluentSpeechConfig(speech_chunk_chars=12)
        capture = UtteranceDetection(
            PCM16Audio(16000, (10,) * 320),
            "ok",
            100,
            100,
        )
        tts = FakeTTS()
        played = []
        rt = FluentConversationRuntime(
            FakeSTT("今日はどう？"),
            tts,
            lambda text: "順調です。次の作業も進めます。",
            config=cfg,
            recorder=lambda: capture,
            player=lambda audio: played.append(audio),
        )
        turn = rt.turn()
        self.assertEqual(turn.state, "ok")
        self.assertEqual(turn.transcript, "今日はどう？")
        self.assertGreaterEqual(len(tts.texts), 2)
        self.assertEqual(len(played), len(tts.texts))
        self.assertEqual(len(rt.history), 1)

    def test_low_confidence_does_not_call_handler(self):
        cfg = FluentSpeechConfig(min_stt_confidence=0.8)
        capture = UtteranceDetection(
            PCM16Audio(16000, (10,) * 320),
            "ok",
            100,
            100,
        )
        called = []
        rt = FluentConversationRuntime(
            FakeSTT("怪しい", 0.2),
            FakeTTS(),
            lambda text: called.append(text) or "返答",
            config=cfg,
            recorder=lambda: capture,
            player=lambda audio: None,
        )
        turn = rt.turn()
        self.assertEqual(turn.state, "low_confidence")
        self.assertEqual(called, [])

    def test_history_is_bounded_and_contains_no_audio(self):
        cfg = FluentSpeechConfig(max_history_turns=2)
        capture = UtteranceDetection(
            PCM16Audio(16000, (10,) * 320),
            "ok",
            100,
            100,
        )
        rt = FluentConversationRuntime(
            FakeSTT(),
            FakeTTS(),
            lambda text: "ok",
            config=cfg,
            recorder=lambda: capture,
            player=lambda audio: None,
        )
        rt.turn()
        rt.turn()
        rt.turn()
        self.assertEqual(len(rt.history), 2)
        self.assertFalse(any(hasattr(turn, "audio") for turn in rt.history))

    def test_local_json_stt_backend_is_shell_free_and_parses_json(self):
        if os.name == "nt":
            self.skipTest("fixture uses POSIX executable script")
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "stt.py"
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'text':'自由発話','confidence':0.88}, ensure_ascii=False))\n",
                encoding="utf-8",
            )
            script.chmod(script.stat().st_mode | stat.S_IEXEC)
            backend = LocalJSONSTTBackend([str(script), "{wav}"])
            result = backend.transcribe_audio(
                PCM16Audio(16000, (0,) * 320)
            )
            self.assertEqual(result.state, "ok")
            self.assertEqual(result.text, "自由発話")
            self.assertAlmostEqual(result.confidence, 0.88)


if __name__ == "__main__":
    unittest.main()
