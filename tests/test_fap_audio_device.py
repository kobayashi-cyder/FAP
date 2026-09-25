import unittest

from fap_audio_device import (
    AdaptiveSoundDeviceIO,
    AudioDeviceUnavailable,
    _mono_rows,
)
from fap_speech import PCM16Audio
from fap_speech_fluent import FluentSpeechConfig


class FakeDefault:
    device = (0, 1)


class FakeInputStream:
    def __init__(self, owner, **kwargs):
        self.owner = owner
        self.kwargs = kwargs
        self.index = 0

    def __enter__(self):
        self.owner.opened_input.append(self.kwargs)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, frame_n):
        frames = self.owner.input_frames
        if self.index < len(frames):
            value = frames[self.index]
            self.index += 1
        else:
            value = 0
        channels = int(self.kwargs["channels"])
        return [[value] * channels for _ in range(frame_n)], False


class FakeSoundDevice:
    def __init__(self):
        self.default = FakeDefault()
        self.devices = [
            {
                "name": "USB Mic 48k stereo",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000.0,
                "default_low_input_latency": 0.012,
            },
            {
                "name": "USB Speaker 44k stereo",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100.0,
                "default_low_output_latency": 0.021,
            },
        ]
        self.input_frames = [10, 10, 1200, 1200, 1200, 5, 5, 5]
        self.opened_input = []
        self.play_calls = []
        self.fail_play_once = False
        self.query_count = 0

    def query_devices(self):
        self.query_count += 1
        return list(self.devices)

    def check_input_settings(self, *, device, samplerate, channels, dtype):
        if device != 0 or samplerate != 48000 or channels != 2 or dtype != "int16":
            raise ValueError("unsupported input mode")

    def check_output_settings(self, *, device, samplerate, channels, dtype):
        if device != 1 or samplerate != 44100 or channels != 2 or dtype != "int16":
            raise ValueError("unsupported output mode")

    def InputStream(self, **kwargs):
        return FakeInputStream(self, **kwargs)

    def play(self, data, samplerate, *, device, blocking):
        if self.fail_play_once:
            self.fail_play_once = False
            raise RuntimeError("device changed")
        self.play_calls.append(
            {
                "frames": len(data),
                "channels": len(data[0]) if data else 0,
                "samplerate": samplerate,
                "device": device,
                "blocking": blocking,
            }
        )


class MissingDefault:
    device = (-1, -1)


class NamedSoundDevice(FakeSoundDevice):
    def __init__(self):
        super().__init__()
        self.default = MissingDefault()


class AudioDeviceCompatibilityTests(unittest.TestCase):
    def test_probe_falls_back_to_native_rates_and_stereo(self):
        sd = FakeSoundDevice()
        io = AdaptiveSoundDeviceIO(
            sounddevice_module=sd,
            canonical_input_rate=16000,
            preferred_output_rate=22050,
        )
        profile = io.refresh()
        self.assertEqual(profile.input_rate, 48000)
        self.assertEqual(profile.input_channels, 2)
        self.assertEqual(profile.output_rate, 44100)
        self.assertEqual(profile.output_channels, 2)
        self.assertEqual(profile.input_name, "USB Mic 48k stereo")
        self.assertEqual(profile.output_name, "USB Speaker 44k stereo")

    def test_record_normalizes_native_48k_stereo_to_16k_mono(self):
        sd = FakeSoundDevice()
        io = AdaptiveSoundDeviceIO(sounddevice_module=sd)
        cfg = FluentSpeechConfig(
            sample_rate=16000,
            frame_ms=20,
            calibration_ms=40,
            trailing_silence_ms=40,
            min_speech_ms=40,
            pre_roll_ms=20,
            absolute_rms_floor=100,
            noise_multiplier=2.0,
            start_timeout_s=2.0,
        )
        result = io.record_utterance(cfg)
        self.assertEqual(result.state, "ok")
        self.assertEqual(result.audio.sample_rate, 16000)
        self.assertTrue(result.audio.samples)
        self.assertEqual(sd.opened_input[0]["samplerate"], 48000)
        self.assertEqual(sd.opened_input[0]["channels"], 2)

    def test_play_resamples_and_expands_mono_to_device_channels(self):
        sd = FakeSoundDevice()
        io = AdaptiveSoundDeviceIO(sounddevice_module=sd)
        io.play(PCM16Audio(22050, (100, -100) * 2205))
        self.assertEqual(len(sd.play_calls), 1)
        call = sd.play_calls[0]
        self.assertEqual(call["samplerate"], 44100)
        self.assertEqual(call["channels"], 2)
        self.assertEqual(call["device"], 1)
        self.assertGreater(call["frames"], 2205)

    def test_device_name_selectors_work_without_defaults(self):
        sd = NamedSoundDevice()
        io = AdaptiveSoundDeviceIO(
            sounddevice_module=sd,
            input_device="usb mic",
            output_device="speaker",
        )
        profile = io.refresh()
        self.assertEqual(profile.input_device, 0)
        self.assertEqual(profile.output_device, 1)

    def test_missing_named_device_fails_closed(self):
        sd = NamedSoundDevice()
        io = AdaptiveSoundDeviceIO(
            sounddevice_module=sd,
            input_device="does-not-exist",
        )
        with self.assertRaises(AudioDeviceUnavailable):
            io.refresh()

    def test_play_error_reprobes_once_and_recovers(self):
        sd = FakeSoundDevice()
        io = AdaptiveSoundDeviceIO(sounddevice_module=sd, reprobe_on_error=True)
        io.refresh()
        before = sd.query_count
        sd.fail_play_once = True
        io.play(PCM16Audio(22050, (100,) * 1000))
        self.assertGreater(sd.query_count, before)
        self.assertEqual(len(sd.play_calls), 1)

    def test_downmix_averages_real_channel_rows(self):
        mono = _mono_rows([[1000, -1000], [3000, 1000]], 2)
        self.assertEqual(mono, (0, 2000))


if __name__ == "__main__":
    unittest.main()
