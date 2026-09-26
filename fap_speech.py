from __future__ import annotations

"""FAP-owned, version-neutral speech I/O.

The module deliberately depends only on the Python standard library for model
inference and WAV I/O. Microphone capture uses optional \`\`sounddevice\`\` because
Python stdlib has no portable recording API. Windows playback uses \`\`winsound\`\`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence
import argparse
import json
import math
import os
import random
import struct
import tempfile
import wave


@dataclass(frozen=True)
class PCM16Audio:
    sample_rate: int
    samples: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if any(x < -32768 or x > 32767 for x in self.samples):
            raise ValueError("samples must be signed PCM16")

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / float(self.sample_rate)


def read_wav(path: str | Path, *, target_rate: int | None = None) -> PCM16Audio:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if width != 2 or channels < 1:
        raise ValueError("FAP speech expects 16-bit PCM WAV")
    vals = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    if channels == 1:
        mono = tuple(vals)
    else:
        mono = tuple(int(sum(vals[i:i + channels]) / channels) for i in range(0, len(vals), channels))
    audio = PCM16Audio(rate, mono)
    return resample(audio, target_rate) if target_rate and target_rate != rate else audio


def write_wav(path: str | Path, audio: PCM16Audio) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = struct.pack("<" + "h" * len(audio.samples), *audio.samples) if audio.samples else b""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(audio.sample_rate)
        wf.writeframes(raw)
    return path


def resample(audio: PCM16Audio, target_rate: int | None) -> PCM16Audio:
    if target_rate is None:
        return audio
    target_rate = int(target_rate)
    if target_rate <= 0:
        raise ValueError("target_rate must be positive")
    if target_rate == audio.sample_rate or not audio.samples:
        return PCM16Audio(target_rate, audio.samples)
    ratio = target_rate / float(audio.sample_rate)
    n = max(1, int(round(len(audio.samples) * ratio)))
    out: list[int] = []
    for i in range(n):
        src = i / ratio
        lo = int(src)
        hi = min(lo + 1, len(audio.samples) - 1)
        frac = src - lo
        value = (1.0 - frac) * audio.samples[lo] + frac * audio.samples[hi]
        out.append(max(-32768, min(32767, int(round(value)))))
    return PCM16Audio(target_rate, tuple(out))


def _goertzel(frame: Sequence[int], rate: int, freq: float) -> float:
    omega = 2.0 * math.pi * freq / rate
    coeff = 2.0 * math.cos(omega)
    s1 = s2 = 0.0
    for sample in frame:
        s0 = float(sample) + coeff * s1 - s2
        s2, s1 = s1, s0
    return max(0.0, s1 * s1 + s2 * s2 - coeff * s1 * s2) / max(1, len(frame))


def acoustic_features(audio: PCM16Audio) -> tuple[float, ...]:
    """Dependency-free acoustic embedding for FAP-STT bootstrap."""
    if not audio.samples:
        return (0.0,) * 22
    rate = audio.sample_rate
    frame_n = max(32, int(rate * 0.025))
    hop = max(16, int(rate * 0.010))
    freqs = (180, 260, 380, 550, 800, 1150, 1650, 2350, 3300)
    rows: list[tuple[float, ...]] = []
    limit = max(1, len(audio.samples) - frame_n + 1)
    for start in range(0, limit, hop):
        frame = audio.samples[start:start + frame_n]
        if len(frame) < frame_n:
            frame += (0,) * (frame_n - len(frame))
        rms = math.sqrt(sum(float(x) * x for x in frame) / len(frame)) / 32768.0
        zc = sum(1 for a, b in zip(frame, frame[1:]) if (a < 0 <= b) or (b < 0 <= a)) / max(1, len(frame) - 1)
        rows.append((math.log1p(rms), zc, *(math.log1p(_goertzel(frame, rate, f)) for f in freqs)))
    means = [sum(r[d] for r in rows) / len(rows) for d in range(len(rows[0]))]
    stds = [math.sqrt(sum((r[d] - means[d]) ** 2 for r in rows) / len(rows)) for d in range(len(rows[0]))]
    return tuple(means + stds)


@dataclass(frozen=True)
class STTResult:
    text: str
    confidence: float
    state: str


class FAPSTTModel:
    """FAP-owned trainable local STT bootstrap.

    It learns acoustic prototypes from labelled WAVs. This provides useful local
    command/phrase recognition now and a stable API for a future neural backend.
    Untrained models fail closed instead of fabricating text.
    """

    FORMAT = "fap.stt.prototype.v1"
    SAMPLE_RATE = 16000

    def __init__(self, prototypes: dict[str, list[tuple[float, ...]]] | None = None) -> None:
        self.prototypes = prototypes or {}

    @property
    def trained(self) -> bool:
        return any(self.prototypes.values())

    def fit(self, examples: Iterable[tuple[str, str | Path]]) -> None:
        learned: dict[str, list[tuple[float, ...]]] = {}
        for label, wav_path in examples:
            label = str(label).strip()
            if not label:
                raise ValueError("empty STT label")
            learned.setdefault(label, []).append(acoustic_features(read_wav(wav_path, target_rate=self.SAMPLE_RATE)))
        if not learned:
            raise ValueError("no STT examples supplied")
        self.prototypes = learned

    def transcribe_audio(self, audio: PCM16Audio) -> STTResult:
        if not self.trained:
            return STTResult("", 0.0, "untrained")
        feature = acoustic_features(resample(audio, self.SAMPLE_RATE))
        scores: list[tuple[float, str]] = []
        for label, rows in self.prototypes.items():
            best = min(math.sqrt(sum((a - b) ** 2 for a, b in zip(feature, row))) for row in rows)
            scores.append((best, label))
        scores.sort(key=lambda x: (x[0], x[1]))
        best, label = scores[0]
        second = scores[1][0] if len(scores) > 1 else best + 1.0
        margin = min(1.0, max(0.0, second - best))
        confidence = max(0.0, min(1.0, (1.0 / (1.0 + best)) * (0.5 + 0.5 * margin)))
        return STTResult(label, confidence, "ok")

    def transcribe_file(self, path: str | Path) -> STTResult:
        return self.transcribe_audio(read_wav(path, target_rate=self.SAMPLE_RATE))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": self.FORMAT, "sample_rate": self.SAMPLE_RATE,
                   "prototypes": {k: [list(v) for v in rows] for k, rows in sorted(self.prototypes.items())}}
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "FAPSTTModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("format") != cls.FORMAT or int(payload.get("sample_rate", 0)) != cls.SAMPLE_RATE:
            raise ValueError("unsupported FAP STT model")
        raw = payload.get("prototypes")
        if not isinstance(raw, dict):
            raise ValueError("invalid STT model")
        return cls({str(k): [tuple(float(x) for x in row) for row in rows] for k, rows in raw.items()})


@dataclass(frozen=True)
class TTSResult:
    audio: PCM16Audio
    state: str = "ok"


_FORMANTS = {
    "a": (800.0, 1150.0, 2900.0), "i": (300.0, 2200.0, 3000.0),
    "u": (350.0, 1200.0, 2400.0), "e": (500.0, 1850.0, 2500.0),
    "o": (500.0, 900.0, 2600.0),
}
_KANA = {}
for _v, _chars in {
    "a": "あかがさざただなはばぱまやらわぁゃアカガサザタダナハバパマヤラワァャ",
    "i": "いきぎしじちぢにひびぴみりゐぃイキギシジチヂニヒビピミリヰィ",
    "u": "うくぐすずつづぬふぶぷむゆるをぅゅウクグスズツヅヌフブプムユルヲゥュ",
    "e": "えけげせぜてでねへべぺめれゑぇエケゲセゼテデネヘベペメレヱェ",
    "o": "おこごそぞとどのほぼぽもよろをぉょオコゴソゾトドノホボポモヨロヲォョ",
}.items():
    _KANA.update({c: _v for c in _chars})


class FAPTTSModel:
    """FAP-owned source/filter synthesizer; no cloud or pretrained voice."""

    FORMAT = "fap.tts.formant.v1"

    def __init__(self, *, sample_rate: int = 22050, char_ms: int = 95, seed: int = 7) -> None:
        if sample_rate < 8000:
            raise ValueError("sample_rate too low")
        self.sample_rate = int(sample_rate)
        self.char_ms = max(35, min(300, int(char_ms)))
        self.seed = int(seed)

    def synthesize(self, text: str) -> TTSResult:
        text = str(text or "")
        if not text:
            return TTSResult(PCM16Audio(self.sample_rate, ()), "empty")
        rng, out, phase = random.Random(self.seed), [], 0.0
        for ch in text[:4096]:
            if ch.isspace() or ch in "、。，,.!?！？":
                out.extend([0] * int(self.sample_rate * (0.065 if ch.isspace() else 0.115)))
                continue
            vowel = _KANA.get(ch) or (ch.lower() if ch.lower() in "aeiou" else None)
            if not vowel:
                n = int(self.sample_rate * min(60, self.char_ms) / 1000.0)
                for i in range(n):
                    env = min(1.0, i / max(1, int(.15*n))) * min(1.0, (n-i) / max(1, int(.25*n)))
                    out.append(int(rng.uniform(-1, 1) * 7000 * env))
                continue
            n, f0 = int(self.sample_rate * self.char_ms / 1000.0), 145.0
            for i in range(n):
                t = i / self.sample_rate
                env = min(1.0, i / max(1, int(.12*n))) * min(1.0, (n-i) / max(1, int(.18*n)))
                buzz = .55*math.sin(phase + 2*math.pi*f0*t) + .25*math.sin(phase + 4*math.pi*f0*t)
                reson = sum((1/(j+1))*math.sin(2*math.pi*f*t) for j, f in enumerate(_FORMANTS[vowel]))
                out.append(int(max(-1.0, min(1.0, env*(.55*buzz + .20*reson))) * 24000))
            phase = (phase + 2*math.pi*f0*(n/self.sample_rate)) % (2*math.pi)
        peak = max((abs(x) for x in out), default=1)
        scale = min(1.0, 28000.0 / peak)
        return TTSResult(PCM16Audio(self.sample_rate, tuple(int(max(-32768, min(32767, x*scale))) for x in out)))

    def synthesize_to_file(self, text: str, path: str | Path) -> Path:
        return write_wav(path, self.synthesize(text).audio)


def play_audio(audio: PCM16Audio) -> None:
    if os.name == "nt":
        import winsound
        fd, name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            write_wav(name, audio)
            winsound.PlaySound(name, winsound.SND_FILENAME)
        finally:
            Path(name).unlink(missing_ok=True)
        return
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("playback requires optional sounddevice on this platform") from exc
    sd.play([x / 32768.0 for x in audio.samples], audio.sample_rate, blocking=True)


def record_audio(seconds: float = 4.0, *, sample_rate: int = 16000) -> PCM16Audio:
    if not 0.1 <= float(seconds) <= 120.0:
        raise ValueError("seconds must be in [0.1,120]")
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("microphone capture requires: pip install sounddevice") from exc
    data = sd.rec(int(round(seconds*sample_rate)), samplerate=sample_rate, channels=1, dtype="int16", blocking=True)
    return PCM16Audio(sample_rate, tuple(int(row[0]) for row in data.tolist()))


TextHandler = Callable[[str], str]


@dataclass
class SpeechRuntime:
    """Stable speech boundary shared by all FAP versions."""
    stt: FAPSTTModel
    tts: FAPTTSModel

    @classmethod
    def bootstrap(cls, *, stt_model_path: str | Path | None = None) -> "SpeechRuntime":
        return cls(FAPSTTModel.load(stt_model_path) if stt_model_path else FAPSTTModel(), FAPTTSModel())

    def transcribe_file(self, path: str | Path) -> STTResult:
        return self.stt.transcribe_file(path)

    def synthesize(self, text: str) -> TTSResult:
        return self.tts.synthesize(text)

    def speak(self, text: str) -> TTSResult:
        result = self.synthesize(text)
        if result.audio.samples:
            play_audio(result.audio)
        return result

    def listen(self, *, seconds: float = 4.0) -> STTResult:
        return self.stt.transcribe_audio(record_audio(seconds, sample_rate=self.stt.SAMPLE_RATE))

    def roundtrip(self, text_handler: TextHandler, *, seconds: float = 4.0) -> tuple[STTResult, str, TTSResult]:
        heard = self.listen(seconds=seconds)
        if heard.state != "ok" or not heard.text:
            return heard, "", TTSResult(PCM16Audio(self.tts.sample_rate, ()), "skipped")
        reply = str(text_handler(heard.text))
        return heard, reply, self.speak(reply)


def wrap_text_handler(handler: TextHandler, runtime: SpeechRuntime | None = None):
    rt = runtime or SpeechRuntime.bootstrap()
    def voice_once(*, seconds: float = 4.0):
        return rt.roundtrip(handler, seconds=seconds)
    return voice_once


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fap_speech")
    p.add_argument("--stt-model")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tts"); t.add_argument("text"); t.add_argument("output")
    s = sub.add_parser("stt"); s.add_argument("wav")
    tr = sub.add_parser("train-stt"); tr.add_argument("output"); tr.add_argument("example", nargs="+")
    sp = sub.add_parser("speak"); sp.add_argument("text")
    li = sub.add_parser("listen"); li.add_argument("--seconds", type=float, default=4.0)
    args = p.parse_args(argv)
    if args.cmd == "train-stt":
        examples = []
        for item in args.example:
            if "=" not in item:
                p.error("STT examples must be label=path.wav")
            label, path = item.split("=", 1); examples.append((label, path))
        model = FAPSTTModel(); model.fit(examples); model.save(args.output); print(args.output); return 0
    rt = SpeechRuntime.bootstrap(stt_model_path=args.stt_model)
    if args.cmd == "tts": print(rt.tts.synthesize_to_file(args.text, args.output)); return 0
    if args.cmd == "stt":
        r = rt.transcribe_file(args.wav); print(r.text); print(f"state={r.state} confidence={r.confidence:.3f}"); return 0 if r.state == "ok" else 2
    if args.cmd == "speak": rt.speak(args.text); return 0
    if args.cmd == "listen":
        r = rt.listen(seconds=args.seconds); print(r.text); print(f"state={r.state} confidence={r.confidence:.3f}"); return 0 if r.state == "ok" else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
