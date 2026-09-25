from __future__ import annotations

"""Device-adaptive audio I/O for FAP speech.

The FAP speech core uses canonical mono PCM16. Real devices are allowed to use
other sample rates, channel counts, block sizes and default-device selections.
This adapter probes the host, chooses a supported configuration, normalizes
capture to the requested canonical rate, and converts TTS output back to the
selected device format. A single re-probe is attempted after a device I/O error
so default-device changes and hot-plug events can recover without restarting
FAP.
"""

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable
import math
import os
import time

from fap_speech import PCM16Audio, play_audio, resample
from fap_speech_fluent import FluentSpeechConfig, UtteranceDetection


_COMMON_RATES = (48000, 44100, 32000, 24000, 22050, 16000, 8000)


@dataclass(frozen=True)
class AudioDeviceProfile:
    input_device: int | None
    output_device: int | None
    input_name: str | None
    output_name: str | None
    input_rate: int | None
    output_rate: int | None
    input_channels: int
    output_channels: int
    frame_ms: int
    input_latency_s: float | None = None
    output_latency_s: float | None = None

    @property
    def has_input(self) -> bool:
        return self.input_device is not None and self.input_rate is not None and self.input_channels > 0

    @property
    def has_output(self) -> bool:
        return self.output_device is not None and self.output_rate is not None and self.output_channels > 0


class AudioDeviceUnavailable(RuntimeError):
    pass


def _as_device_pair(value: Any) -> tuple[int | None, int | None]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return _to_index(value[0]), _to_index(value[1])
    idx = _to_index(value)
    return idx, idx


def _to_index(value: Any) -> int | None:
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    return idx if idx >= 0 else None


def _device_name(info: Any) -> str:
    if isinstance(info, dict):
        return str(info.get("name") or "")
    try:
        return str(info["name"])
    except Exception:
        return ""


def _device_value(info: Any, key: str, default: Any = None) -> Any:
    if isinstance(info, dict):
        return info.get(key, default)
    try:
        return info[key]
    except Exception:
        return default


def _candidate_rates(preferred: int | None, device_default: Any) -> tuple[int, ...]:
    values: list[int] = []
    for raw in (preferred, device_default, *_COMMON_RATES):
        try:
            rate = int(round(float(raw)))
        except (TypeError, ValueError):
            continue
        if rate >= 8000 and rate not in values:
            values.append(rate)
    return tuple(values)


def _mono_rows(data: Any, channels: int) -> tuple[int, ...]:
    """Convert sounddevice/numpy-like frame rows to canonical mono PCM16."""
    if hasattr(data, "tolist"):
        data = data.tolist()
    out: list[int] = []
    for row in data:
        if isinstance(row, (list, tuple)):
            vals = [int(x) for x in row[:max(1, channels)]]
            value = int(round(sum(vals) / max(1, len(vals))))
        else:
            value = int(row)
        out.append(max(-32768, min(32767, value)))
    return tuple(out)


def _output_rows(samples: Iterable[int], channels: int) -> list[list[int]]:
    channels = max(1, int(channels))
    return [[int(sample)] * channels for sample in samples]


class AdaptiveSoundDeviceIO:
    """Probe-driven host audio adapter with one-shot hot-plug recovery."""

    def __init__(
        self,
        *,
        sounddevice_module: Any | None = None,
        input_device: int | str | None = None,
        output_device: int | str | None = None,
        canonical_input_rate: int = 16000,
        preferred_output_rate: int | None = None,
        frame_ms: int = 20,
        reprobe_on_error: bool = True,
    ):
        self._sd = sounddevice_module
        self.input_selector = input_device
        self.output_selector = output_device
        self.canonical_input_rate = int(canonical_input_rate)
        self.preferred_output_rate = int(preferred_output_rate) if preferred_output_rate else None
        self.frame_ms = int(frame_ms)
        self.reprobe_on_error = bool(reprobe_on_error)
        self._profile: AudioDeviceProfile | None = None

    def _module(self):
        if self._sd is not None:
            return self._sd
        try:
            import sounddevice as sd  # type: ignore
        except ImportError as exc:
            raise AudioDeviceUnavailable("host audio requires optional sounddevice") from exc
        self._sd = sd
        return sd

    @property
    def profile(self) -> AudioDeviceProfile:
        if self._profile is None:
            self._profile = self.probe()
        return self._profile

    def refresh(self) -> AudioDeviceProfile:
        self._profile = self.probe()
        return self._profile

    def _devices(self) -> list[Any]:
        raw = self._module().query_devices()
        if isinstance(raw, dict):
            return [raw]
        return list(raw)

    @staticmethod
    def _resolve_selector(
        devices: list[Any],
        selector: int | str | None,
        *,
        direction: str,
        default_index: int | None,
    ) -> int | None:
        key = "max_input_channels" if direction == "input" else "max_output_channels"

        def valid(idx: int | None) -> bool:
            return (
                idx is not None
                and 0 <= idx < len(devices)
                and int(_device_value(devices[idx], key, 0) or 0) > 0
            )

        if isinstance(selector, int):
            if not valid(selector):
                raise AudioDeviceUnavailable(f"selected {direction} device is unavailable")
            return selector
        if isinstance(selector, str) and selector.strip():
            needle = selector.casefold()
            for idx, info in enumerate(devices):
                if needle in _device_name(info).casefold() and valid(idx):
                    return idx
            raise AudioDeviceUnavailable(f"selected {direction} device name was not found")
        if valid(default_index):
            return default_index
        for idx, _info in enumerate(devices):
            if valid(idx):
                return idx
        return None

    def _find_settings(
        self,
        *,
        direction: str,
        device: int | None,
        preferred_rate: int | None,
    ) -> tuple[int | None, int, float | None]:
        if device is None:
            return None, 0, None
        sd = self._module()
        info = self._devices()[device]
        max_key = "max_input_channels" if direction == "input" else "max_output_channels"
        latency_key = "default_low_input_latency" if direction == "input" else "default_low_output_latency"
        max_channels = max(0, int(_device_value(info, max_key, 0) or 0))
        if max_channels <= 0:
            return None, 0, None

        # Prefer mono. Some devices/drivers reject mono even when they expose >=1
        # channels, so stereo is the second candidate when available.
        channel_candidates = [1]
        if max_channels >= 2:
            channel_candidates.append(2)
        default_rate = _device_value(info, "default_samplerate")
        checker = sd.check_input_settings if direction == "input" else sd.check_output_settings
        for rate in _candidate_rates(preferred_rate, default_rate):
            for channels in channel_candidates:
                try:
                    checker(device=device, samplerate=rate, channels=channels, dtype="int16")
                except Exception:
                    continue
                latency = _device_value(info, latency_key)
                try:
                    latency = float(latency)
                except (TypeError, ValueError):
                    latency = None
                return rate, channels, latency
        return None, 0, None

    def probe(self) -> AudioDeviceProfile:
        sd = self._module()
        devices = self._devices()
        default_in, default_out = _as_device_pair(getattr(sd.default, "device", None))
        input_index = self._resolve_selector(
            devices, self.input_selector, direction="input", default_index=default_in
        )
        output_index = self._resolve_selector(
            devices, self.output_selector, direction="output", default_index=default_out
        )
        input_rate, input_channels, input_latency = self._find_settings(
            direction="input", device=input_index, preferred_rate=self.canonical_input_rate
        )
        output_rate, output_channels, output_latency = self._find_settings(
            direction="output", device=output_index, preferred_rate=self.preferred_output_rate
        )
        return AudioDeviceProfile(
            input_device=input_index if input_rate else None,
            output_device=output_index if output_rate else None,
            input_name=_device_name(devices[input_index]) if input_index is not None else None,
            output_name=_device_name(devices[output_index]) if output_index is not None else None,
            input_rate=input_rate,
            output_rate=output_rate,
            input_channels=input_channels,
            output_channels=output_channels,
            frame_ms=self.frame_ms,
            input_latency_s=input_latency,
            output_latency_s=output_latency,
        )

    @staticmethod
    def _rms(samples: tuple[int, ...]) -> float:
        if not samples:
            return 0.0
        return math.sqrt(sum(float(x) * x for x in samples) / len(samples))

    def _record_once(self, config: FluentSpeechConfig) -> UtteranceDetection:
        sd = self._module()
        profile = self.profile
        if not profile.has_input:
            raise AudioDeviceUnavailable("no compatible audio input device")
        source_rate = int(profile.input_rate)
        frame_n = max(1, int(round(source_rate * config.frame_ms / 1000.0)))
        calibration_frames = max(1, config.calibration_ms // config.frame_ms)
        min_speech_frames = max(1, math.ceil(config.min_speech_ms / config.frame_ms))
        trailing_frames = max(1, math.ceil(config.trailing_silence_ms / config.frame_ms))
        pre_roll_frames = max(0, math.ceil(config.pre_roll_ms / config.frame_ms))
        start_deadline = time.monotonic() + config.start_timeout_s
        hard_deadline = None
        buffered: list[tuple[int, ...]] = []
        noise_values: list[float] = []
        started = False
        speech_run = 0
        silent_run = 0
        threshold = config.absolute_rms_floor
        speech_frames = 0
        overflow_count = 0

        with sd.InputStream(
            samplerate=source_rate,
            channels=profile.input_channels,
            dtype="int16",
            blocksize=frame_n,
            device=profile.input_device,
            latency="low",
        ) as stream:
            while True:
                now = time.monotonic()
                if not started and now >= start_deadline:
                    return UtteranceDetection(
                        PCM16Audio(config.sample_rate, ()), "timeout", threshold, 0
                    )
                if started and hard_deadline is not None and now >= hard_deadline:
                    break
                data, overflowed = stream.read(frame_n)
                if overflowed:
                    overflow_count += 1
                    # A few transient overruns are recoverable. Persistent overruns
                    # indicate that the selected path is not usable in real time.
                    if overflow_count >= 8:
                        raise AudioDeviceUnavailable("persistent input overflow")
                frame = _mono_rows(data, profile.input_channels)
                rms = self._rms(frame)
                buffered.append(frame)

                if not started:
                    if len(noise_values) < calibration_frames:
                        noise_values.append(rms)
                        threshold = max(
                            config.absolute_rms_floor,
                            median(noise_values) * config.noise_multiplier,
                        )
                    if rms >= threshold:
                        speech_run += 1
                        if speech_run >= min_speech_frames:
                            started = True
                            hard_deadline = time.monotonic() + config.max_utterance_s
                            buffered = buffered[-(pre_roll_frames + speech_run):]
                            speech_frames = speech_run
                    else:
                        speech_run = 0
                        max_keep = pre_roll_frames + calibration_frames
                        if len(buffered) > max_keep:
                            buffered = buffered[-max_keep:]
                    continue

                if rms >= threshold:
                    silent_run = 0
                    speech_frames += 1
                else:
                    silent_run += 1
                    if silent_run >= trailing_frames:
                        break

        source_audio = PCM16Audio(source_rate, tuple(x for frame in buffered for x in frame))
        canonical = resample(source_audio, config.sample_rate)
        return UtteranceDetection(canonical, "ok", threshold, speech_frames * config.frame_ms)

    def record_utterance(self, config: FluentSpeechConfig | None = None) -> UtteranceDetection:
        cfg = (config or FluentSpeechConfig(sample_rate=self.canonical_input_rate)).validate()
        try:
            return self._record_once(cfg)
        except Exception:
            if not self.reprobe_on_error:
                raise
            self.refresh()
            return self._record_once(cfg)

    def _play_once(self, audio: PCM16Audio) -> None:
        if not audio.samples:
            return
        profile = self.profile
        if not profile.has_output:
            if os.name == "nt":
                play_audio(audio)
                return
            raise AudioDeviceUnavailable("no compatible audio output device")
        sd = self._module()
        device_audio = resample(audio, int(profile.output_rate))
        rows = _output_rows(device_audio.samples, profile.output_channels)
        sd.play(
            rows,
            int(profile.output_rate),
            device=profile.output_device,
            blocking=True,
        )

    def play(self, audio: PCM16Audio) -> None:
        try:
            self._play_once(audio)
        except Exception:
            if not self.reprobe_on_error:
                raise
            self.refresh()
            self._play_once(audio)


def build_device_adaptive_runtime(
    stt: Any,
    tts: Any,
    handler: Any,
    *,
    config: FluentSpeechConfig | None = None,
    input_device: int | str | None = None,
    output_device: int | str | None = None,
    sounddevice_module: Any | None = None,
):
    """Build FluentConversationRuntime bound to the probed real device path."""
    from fap_speech_fluent import FluentConversationRuntime

    cfg = (config or FluentSpeechConfig()).validate()
    io = AdaptiveSoundDeviceIO(
        sounddevice_module=sounddevice_module,
        input_device=input_device,
        output_device=output_device,
        canonical_input_rate=cfg.sample_rate,
        preferred_output_rate=getattr(tts, "sample_rate", None),
        frame_ms=cfg.frame_ms,
    )
    # Probe eagerly so configuration/device errors are reported before the first
    # conversation turn.
    io.refresh()
    runtime = FluentConversationRuntime(
        stt,
        tts,
        handler,
        config=cfg,
        recorder=lambda: io.record_utterance(cfg),
        player=io.play,
    )
    runtime.audio_io = io
    return runtime
