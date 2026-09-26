import math
from pathlib import Path
import tempfile
import unittest

from fap_speech import (
    FAPSTTModel,
    FAPTTSModel,
    PCM16Audio,
    SpeechRuntime,
    read_wav,
    write_wav,
    wrap_text_handler,
)


class FAPSpeechTests(unittest.TestCase):
    def test_tts_deterministic_nonempty(self):
        model = FAPTTSModel()
        a = model.synthesize("あいうえお").audio
        b = model.synthesize("あいうえお").audio
        self.assertEqual(a, b)
        self.assertGreater(len(a.samples), 1000)
        self.assertGreater(max(abs(x) for x in a.samples), 0)

    def test_wav_roundtrip(self):
        audio = PCM16Audio(
            16000,
            tuple(int(1000 * math.sin(i / 10)) for i in range(500)),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.wav"
            write_wav(path, audio)
            self.assertEqual(read_wav(path), audio)

    def test_untrained_stt_fails_closed(self):
        result = FAPSTTModel().transcribe_audio(
            PCM16Audio(16000, (0,) * 1600)
        )
        self.assertEqual((result.text, result.state), ("", "untrained"))

    def test_stt_train_save_load_classify(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            def tone(freq):
                return PCM16Audio(
                    16000,
                    tuple(
                        int(
                            8000
                            * math.sin(
                                2 * math.pi * freq * i / 16000
                            )
                        )
                        for i in range(8000)
                    ),
                )

            low, high = tone(260), tone(800)
            pa, pb = root / "a.wav", root / "b.wav"
            write_wav(pa, low)
            write_wav(pb, high)

            model = FAPSTTModel()
            model.fit([("low", pa), ("high", pb)])
            loaded = FAPSTTModel.load(
                model.save(root / "model.json")
            )

            self.assertEqual(
                loaded.transcribe_audio(low).text,
                "low",
            )
            self.assertEqual(
                loaded.transcribe_audio(high).text,
                "high",
            )

    def test_version_neutral_text_wrapper(self):
        runtime = SpeechRuntime(
            FAPSTTModel(),
            FAPTTSModel(),
        )
        wrapped = wrap_text_handler(
            lambda text: text.upper(),
            runtime,
        )
        self.assertTrue(callable(wrapped))


if __name__ == "__main__":
    unittest.main()
