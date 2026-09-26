# FAP 1.x speech I/O

`fap_speech.py` provides the public 1.x speech boundary. The boundary accepts a
plain `str -> str` text handler, so speech stays decoupled from the HTTP gateway
and platform UI.

## Implemented

- **FAP-TTS v1**: dependency-free source/filter formant synthesis. It is local,
  intentionally simple, and does not claim neural-voice quality.
- **FAP-STT v1**: dependency-free trainable acoustic-prototype recognition for
  bounded command/phrase sets. An untrained model fails closed instead of
  fabricating text.
- **SpeechRuntime**: WAV transcription, TTS, playback, microphone input, and
  voice roundtrips.
- **wrap_text_handler(handler)**: adapts the canonical 1.x text handler to
  microphone -> STT -> FAP -> TTS.

Python stdlib is sufficient for the core models. Portable microphone capture
uses optional `sounddevice`; Windows playback may use `winsound`.

## 1.x example

```python
from fap_runtime_1x import chat
from fap_speech import SpeechRuntime, wrap_text_handler

runtime = SpeechRuntime.bootstrap(stt_model_path="runtime/fap-stt.json")
voice_once = wrap_text_handler(chat, runtime)
voice_once(seconds=4.0)
```

## Fluent conversation layer

`fap_speech_fluent.py` adds adaptive RMS voice-activity detection, pre-roll,
automatic trailing-silence turn completion, bounded capture duration,
clause-sized TTS chunks, cooperative interruption, bounded text-only history,
confidence gating, and a shell-free local recognizer adapter.

The current acoustic-prototype STT is not an unrestricted dictation model.
True sub-chunk barge-in, echo cancellation, simultaneous full duplex, and
device-specific latency remain unverified until measured on real audio hardware.

The active 1.x tree therefore distinguishes unit/device-abstraction evidence
from real-hardware speech evidence.
