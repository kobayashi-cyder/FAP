# FAP universal speech I/O

\`fap_speech.py\` is deliberately independent of FAP version numbers. Historical
V47/V54/V78/V87.x gateways and the reset 1.x line can share the same speech
boundary as long as their chat entrypoint is a plain \`str -> str\` callable.

## Implemented now

- **FAP-TTS v1**: FAP-owned dependency-free source/filter formant synthesizer.
  It does not call a cloud TTS service and does not load a pretrained third-party
  voice. Output is intentionally simple/robotic but is fully local.
- **FAP-STT v1**: FAP-owned dependency-free trainable acoustic-prototype model.
  It learns labelled local WAV examples and is suitable for commands and bounded
  phrase sets. If no model has been trained it fails closed with
  \`state=untrained\` instead of fabricating text.
- **SpeechRuntime**: stable version-neutral API for WAV transcription, TTS,
  playback, microphone input, and voice roundtrips.
- **wrap_text_handler(handler)**: adapts any FAP text handler into
  microphone -> STT -> FAP -> TTS without importing a version-specific gateway.

The speech models themselves use only Python stdlib. Microphone capture requires
the optional \`sounddevice\` package because Python stdlib has no portable audio
recording API. Windows playback uses \`winsound\`; non-Windows playback can use
\`sounddevice\`.

## Examples

Create a WAV:

\`\`\`bash
python fap_speech.py tts "こんにちは" runtime/hello.wav
\`\`\`

Train the independent STT bootstrap from local examples:

\`\`\`bash
python fap_speech.py train-stt runtime/fap-stt.json \
  "開始=data/start-01.wav" "開始=data/start-02.wav" \
  "停止=data/stop-01.wav" "停止=data/stop-02.wav"
\`\`\`

Transcribe:

\`\`\`bash
python fap_speech.py --stt-model runtime/fap-stt.json stt data/query.wav
\`\`\`

Attach speech to any FAP version:

\`\`\`python
from fap_speech import SpeechRuntime, wrap_text_handler
from some_fap_version import chat

runtime = SpeechRuntime.bootstrap(
    stt_model_path="runtime/fap-stt.json",
)
voice_once = wrap_text_handler(chat, runtime)
voice_once(seconds=4.0)
\`\`\`

## Scope and next model stage

This commit establishes a real independent local TTS path and a trainable STT
bootstrap, but it does **not** claim open-dictation quality yet. The STT backend
is intentionally small and measurable. A future FAP-specific neural
encoder/decoder can replace \`FAPSTTModel\` behind the same API after a speech
corpus is collected and evaluated. The same contract allows a learned acoustic
model/vocoder to replace the formant TTS without changing old FAP versions.
