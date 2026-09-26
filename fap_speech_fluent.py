from __future__ import annotations

"""Low-latency conversational speech orchestration for FAP.

This module is additive to fap_speech.py. It does not replace the existing
independent STT/TTS implementations; instead it turns any compatible STT/TTS
backend into an automatic-turn conversation loop with VAD, bounded text history,
chunked speech output and cooperative interruption.

Raw microphone audio is never retained in conversation history.
"""

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Callable, Protocol
import json
import math
import os
import subprocess
import tempfile
import threading
import time

from fap_speech import PCM16Audio, STTResult, TTSResult, play_audio, write_wav


class STTBackend(Protocol):
    def transcribe_audio(self, audio: PCM16Audio) -> STTResult: ...


class TTSBackend(Protocol):
    sample_rate: int
    def synthesize(self, text: str) -> TTSResult: ...


@dataclass(frozen=True)
class FluentSpeechConfig:
    sample_rate: int = 16000
    frame_ms: int = 20
    calibration_ms: int = 300
    start_timeout_s: float = 8.0
    max_utterance_s: float = 30.0
    trailing_silence_ms: int = 520
    min_speech_ms: int = 120
    pre_roll_ms: int = 160
    noise_multiplier: float = 3.0
    absolute_rms_floor: float = 180.0
    min_stt_confidence: float = 0.0
    max_history_turns: int = 12
    speech_chunk_chars: int = 72

    def validate(self) -> "FluentSpeechConfig":
        if self.sample_rate < 8000:
            raise ValueError("sample_rate must be >= 8000")
        if not 10 <= self.frame_ms <= 100:
            raise ValueError("frame_ms must be in [10, 100]")
        if self.calibration_ms < self.frame_ms:
            raise ValueError("calibration_ms must cover at least one frame")
        if not 0.2 <= self.start_timeout_s <= 120.0:
            raise ValueError("start_timeout_s out of range")
        if not 0.5 <= self.max_utterance_s <= 300.0:
            raise ValueError("max_utterance_s out of range")
        if self.trailing_silence_ms < self.frame_ms:
            raise ValueError("trailing_silence_ms too small")
        if self.min_speech_ms < self.frame_ms:
            raise ValueError("min_speech_ms too small")
        if self.pre_roll_ms < 0:
            raise ValueError("pre_roll_ms must be non-negative")
        if self.noise_multiplier <= 1.0:
            raise ValueError("noise_multiplier must be > 1")
        if self.absolute_rms_floor < 0:
            raise ValueError("absolute_rms_floor must be non-negative")
        if not 0.0 <= self.min_stt_confidence <= 1.0:
            raise ValueError("min_stt_confidence must be in [0, 1]")
        if self.max_history_turns < 1:
            raise ValueError("max_history_turns must be positive")
        if self.speech_chunk_chars < 8:
            raise ValueError("speech_chunk_chars too small")
        return self

    @property
    def frame_samples(self) -> int:
        return max(1, int(round(self.sample_rate * self.frame_ms / 1000.0)))


@dataclass(frozen=True)
class UtteranceDetection:
    audio: PCM16Audio
    state: str
    threshold_rms: float
    speech_ms: int


def _frame_rms(samples: tuple[int, ...] | list[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(float(x) * x for x in samples) / len(samples))


def detect_utterance(audio: PCM16Audio, config: FluentSpeechConfig | None = None) -> UtteranceDetection:
    """Find one utterance in PCM16 using an adaptive RMS noise floor."""
    cfg = (config or FluentSpeechConfig(sample_rate=audio.sample_rate)).validate()
    if audio.sample_rate != cfg.sample_rate:
        raise ValueError("audio sample_rate must match config")
    n = cfg.frame_samples
    frames = [audio.samples[i:i+n] for i in range(0, len(audio.samples), n)]
    if not frames:
        return UtteranceDetection(PCM16Audio(audio.sample_rate, ()), "no_audio", cfg.absolute_rms_floor, 0)

    calibration_frames = max(1, cfg.calibration_ms // cfg.frame_ms)
    noise_window = [_frame_rms(f) for f in frames[:calibration_frames]]
    noise = median(noise_window) if noise_window else 0.0
    threshold = max(cfg.absolute_rms_floor, noise * cfg.noise_multiplier)
    min_speech_frames = max(1, math.ceil(cfg.min_speech_ms / cfg.frame_ms))
    trailing_frames = max(1, math.ceil(cfg.trailing_silence_ms / cfg.frame_ms))
    pre_roll_frames = max(0, math.ceil(cfg.pre_roll_ms / cfg.frame_ms))

    run = 0
    start = None
    for i, frame in enumerate(frames):
        if _frame_rms(frame) >= threshold:
            run += 1
            if run >= min_speech_frames:
                start = max(0, i - run + 1 - pre_roll_frames)
                break
        else:
            run = 0
    if start is None:
        return UtteranceDetection(PCM16Audio(audio.sample_rate, ()), "no_speech", threshold, 0)

    silent = 0
    last_speech = start
    end = len(frames)
    for i in range(start, len(frames)):
        if _frame_rms(frames[i]) >= threshold:
            silent = 0
            last_speech = i
        else:
            silent += 1
            if silent >= trailing_frames:
                end = min(len(frames), last_speech + 1 + trailing_frames)
                break

    selected = tuple(x for frame in frames[start:end] for x in frame)
    speech_frames = max(1, last_speech - start + 1)
    return UtteranceDetection(
        PCM16Audio(audio.sample_rate, selected),
        "ok",
        threshold,
        speech_frames * cfg.frame_ms,
    )


def record_utterance(config: FluentSpeechConfig | None = None) -> UtteranceDetection:
    """Capture one microphone utterance and return after sustained trailing silence."""
    cfg = (config or FluentSpeechConfig()).validate()
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("automatic microphone turns require: pip install sounddevice") from exc

    frame_n = cfg.frame_samples
    calibration_frames = max(1, cfg.calibration_ms // cfg.frame_ms)
    min_speech_frames = max(1, math.ceil(cfg.min_speech_ms / cfg.frame_ms))
    trailing_frames = max(1, math.ceil(cfg.trailing_silence_ms / cfg.frame_ms))
    pre_roll_frames = max(0, math.ceil(cfg.pre_roll_ms / cfg.frame_ms))
    start_deadline = time.monotonic() + cfg.start_timeout_s
    hard_deadline = None
    buffered: list[tuple[int, ...]] = []
    noise_values: list[float] = []
    started = False
    speech_run = 0
    silent_run = 0
    threshold = cfg.absolute_rms_floor
    speech_frames = 0

    with sd.InputStream(samplerate=cfg.sample_rate, channels=1, dtype="int16", blocksize=frame_n) as stream:
        while True:
            now = time.monotonic()
            if not started and now >= start_deadline:
                return UtteranceDetection(PCM16Audio(cfg.sample_rate, ()), "timeout", threshold, 0)
            if started and hard_deadline is not None and now >= hard_deadline:
                break

            data, _overflowed = stream.read(frame_n)
            frame = tuple(int(row[0]) for row in data.tolist())
            rms = _frame_rms(frame)
            buffered.append(frame)

            if not started:
                if len(noise_values) < calibration_frames:
                    noise_values.append(rms)
                    noise = median(noise_values)
                    threshold = max(cfg.absolute_rms_floor, noise * cfg.noise_multiplier)
                if rms >= threshold:
                    speech_run += 1
                    if speech_run >= min_speech_frames:
                        started = True
                        hard_deadline = time.monotonic() + cfg.max_utterance_s
                        keep = pre_roll_frames + speech_run
                        buffered = buffered[-keep:]
                        speech_frames = speech_run
                else:
                    speech_run = 0
                    if len(buffered) > pre_roll_frames + calibration_frames:
                        buffered = buffered[-(pre_roll_frames + calibration_frames):]
                continue

            if rms >= threshold:
                silent_run = 0
                speech_frames += 1
            else:
                silent_run += 1
                if silent_run >= trailing_frames:
                    break

    samples = tuple(x for frame in buffered for x in frame)
    return UtteranceDetection(PCM16Audio(cfg.sample_rate, samples), "ok", threshold, speech_frames * cfg.frame_ms)


def split_for_speech(text: str, *, max_chars: int = 72) -> list[str]:
    """Split a response into speakable clauses to reduce time-to-first-audio."""
    text = " ".join(str(text).split())
    if not text:
        return []
    if max_chars < 8:
        raise ValueError("max_chars too small")

    pieces: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。！？!?、,；;：:" and len(buf) >= 4:
            pieces.append(buf.strip())
            buf = ""
    if buf.strip():
        pieces.append(buf.strip())

    out: list[str] = []
    for piece in pieces:
        while len(piece) > max_chars:
            cut = piece.rfind(" ", 0, max_chars + 1)
            if cut < max_chars // 2:
                cut = max_chars
            out.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            out.append(piece)
    return out


@dataclass(frozen=True)
class VoiceTurn:
    transcript: str
    response: str
    stt_confidence: float
    state: str
    started_at: float
    finished_at: float

    @property
    def latency_ms(self) -> int:
        return max(0, int(round((self.finished_at - self.started_at) * 1000)))


class LocalJSONSTTBackend:
    """Safe adapter for a local free-dictation process.

    The configured command must contain exactly one {wav} placeholder and emit
    one JSON object to stdout with text and optional confidence fields.
    shell=False is always used.
    """

    SAMPLE_RATE = 16000

    def __init__(self, command: list[str] | tuple[str, ...], *, timeout_s: float = 45.0,
                 max_stdout_bytes: int = 1_000_000):
        self.command = tuple(str(x) for x in command)
        if sum(part.count("{wav}") for part in self.command) != 1:
            raise ValueError("local STT command must contain exactly one {wav} placeholder")
        if not self.command or not os.path.isabs(self.command[0]):
            raise ValueError("local STT executable must be an absolute path")
        if not 0.1 <= timeout_s <= 300.0:
            raise ValueError("timeout_s out of range")
        self.timeout_s = float(timeout_s)
        self.max_stdout_bytes = int(max_stdout_bytes)

    def transcribe_audio(self, audio: PCM16Audio) -> STTResult:
        with tempfile.TemporaryDirectory(prefix="fap-stt-") as td:
            wav = Path(td) / "utterance.wav"
            write_wav(wav, audio)
            argv = [p.replace("{wav}", str(wav)) for p in self.command]
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_s,
                check=False,
                shell=False,
            )
            if completed.returncode != 0:
                return STTResult("", 0.0, "backend_error")
            if len(completed.stdout) > self.max_stdout_bytes:
                return STTResult("", 0.0, "backend_oversize")
            try:
                payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return STTResult("", 0.0, "backend_invalid_json")
            text = payload.get("text") if isinstance(payload, dict) else None
            confidence = payload.get("confidence", 1.0) if isinstance(payload, dict) else 0.0
            if not isinstance(text, str) or not text.strip():
                return STTResult("", 0.0, "empty")
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.0
            return STTResult(text.strip(), confidence, "ok")


class FluentConversationRuntime:
    """Automatic half-duplex FAP conversation with low perceived latency."""

    def __init__(
        self,
        stt: STTBackend,
        tts: TTSBackend,
        handler: Callable[[str], str],
        *,
        config: FluentSpeechConfig | None = None,
        recorder: Callable[[], UtteranceDetection] | None = None,
        player: Callable[[PCM16Audio], None] = play_audio,
    ):
        self.stt = stt
        self.tts = tts
        self.handler = handler
        self.config = (config or FluentSpeechConfig()).validate()
        self.recorder = recorder or (lambda: record_utterance(self.config))
        self.player = player
        self._stop = threading.Event()
        self._interrupt = threading.Event()
        self.history: list[VoiceTurn] = []

    def stop(self) -> None:
        self._stop.set()
        self._interrupt.set()

    def interrupt(self) -> None:
        self._interrupt.set()

    def clear_interrupt(self) -> None:
        self._interrupt.clear()

    def _remember(self, turn: VoiceTurn) -> None:
        self.history.append(turn)
        if len(self.history) > self.config.max_history_turns:
            self.history = self.history[-self.config.max_history_turns:]

    def speak_chunked(self, text: str) -> int:
        spoken = 0
        self._interrupt.clear()
        for chunk in split_for_speech(text, max_chars=self.config.speech_chunk_chars):
            if self._stop.is_set() or self._interrupt.is_set():
                break
            result = self.tts.synthesize(chunk)
            if result.state != "ok" or not result.audio.samples:
                continue
            self.player(result.audio)
            spoken += 1
        return spoken

    def turn(self) -> VoiceTurn:
        started = time.monotonic()
        captured = self.recorder()
        if captured.state != "ok" or not captured.audio.samples:
            turn = VoiceTurn("", "", 0.0, captured.state, started, time.monotonic())
            self._remember(turn)
            return turn

        heard = self.stt.transcribe_audio(captured.audio)
        if heard.state != "ok" or not heard.text.strip():
            turn = VoiceTurn("", "", heard.confidence, heard.state, started, time.monotonic())
            self._remember(turn)
            return turn
        if heard.confidence < self.config.min_stt_confidence:
            turn = VoiceTurn(heard.text.strip(), "", heard.confidence, "low_confidence", started, time.monotonic())
            self._remember(turn)
            return turn

        transcript = heard.text.strip()
        response = str(self.handler(transcript)).strip()
        if not response:
            turn = VoiceTurn(transcript, "", heard.confidence, "empty_response", started, time.monotonic())
            self._remember(turn)
            return turn

        self.speak_chunked(response)
        turn = VoiceTurn(
            transcript,
            response,
            heard.confidence,
            "interrupted" if self._interrupt.is_set() else "ok",
            started,
            time.monotonic(),
        )
        self._remember(turn)
        return turn

    def run(
        self,
        *,
        max_turns: int | None = None,
        stop_phrases: tuple[str, ...] = ("終了", "会話終了", "ストップ"),
    ) -> list[VoiceTurn]:
        count = 0
        while not self._stop.is_set() and (max_turns is None or count < max_turns):
            turn = self.turn()
            count += 1
            if turn.transcript and any(p in turn.transcript for p in stop_phrases):
                break
        return list(self.history)
