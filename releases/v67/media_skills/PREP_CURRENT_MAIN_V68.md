# Audio Input Skill — current-main preparation addendum

Reviewed against main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

Next safe step: validate bounded PCM/audio input and isolate transcription behind `STTAdapter`. Test malformed format/rate/channels, zero-length/silent fixture, missing STT provider, timeout/error, empty transcript, malformed provider payload and lifecycle cancellation. A VAD/signal result is not transcription; STT claims require an independently exercised concrete adapter.

Android: RECORD_AUDIO permission, explicit mic start/stop, cancellation/background transition and mic-release behavior must be adapter/lifecycle tests. No always-on mic. Audio is ephemeral by default; evidence should use synthetic fixtures and avoid retaining user recordings/transcripts. Measure audio bytes/sec, STT latency, peak RAM and capture duration bounds.

Promotion requires reproducible STT adapter evidence plus current-main regression. DEFER wake-word, streaming STT and continuous listening. REPLACE if a proven sibling-neutral audio contract supersedes this interface.