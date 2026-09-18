# V80 PREP — Android/host microphone and audio-output lifecycle

Base / rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (actual main, V77 KEEP). Independent of V78/V79 and media sibling branches.

## Candidate boundary
Platform lifecycle only: bounded microphone capture source and bounded audio-output sink abstractions plus Android/host lifecycle glue. No STT/TTS backend and no generation/transcription/synthesis claim.

Expected interfaces/files: `MicSource.start/read/stop/release`, `AudioSink.open/write/stop/release`, lifecycle state enum, cancellation token, bounded PCM/frame buffer configuration, Android permission/focus adapter, host test doubles, lifecycle/resource tests. Provider-neutral audio bytes cross the boundary; no provider SDK belongs here.

## Android lifecycle
Request `RECORD_AUDIO` only immediately before explicit capture; denial, denial-with-dont-ask-again and runtime revocation must fail closed. Start only after grant. Stop/release on user stop, cancellation, activity/service teardown, device/input loss and error. Audio output must request the appropriate transient focus only when playback begins, handle focus loss/interruption, abandon focus on every terminal path and release the sink. No background mic by default; visible/user-initiated session required.

## Negative tests
Permission denied/revoked; duplicate start/stop/release; read/write before start/open; cancellation at each state; focus denied/lost; device disconnect; zero/partial/oversized frame; unsupported sample format/rate/channels; buffer overflow/underflow; output failure; activity recreation; repeated 100-cycle start/stop; exception during cleanup. Terminal cleanup must be idempotent.

## Privacy / retention / resources
Raw microphone/output bytes are memory-only by default and discarded after bounded handoff/playback. No recording file, telemetry or transcript logging by default. Explicit export is separate and out of scope. Measure startup/stop latency, peak RSS delta, bounded buffer high-water mark and retained storage (expected zero); on Android also capture repeated-cycle resource stability. Never estimate missing metrics.

## Promotion evidence
Deterministic host lifecycle tests plus Android instrumentation evidence for permission grant/deny/revoke, focus acquire/loss/abandon, mic start/stop/release, output release and repeated-cycle cleanup. Compile/import checks and applicable core regressions pass without hidden skips. Evidence must show no capture before permission and no retained raw audio after terminal cleanup.

## DEFER / REPLACE
DEFER Android KEEP if no device/emulator path can independently exercise permission/focus/lifecycle behavior; host abstractions may remain truthful platform-neutral preparation. REPLACE/split any backend-specific STT/TTS or image dependency. Disable/rollback on privacy leak, capture after revocation, focus leak, non-idempotent cleanup, unbounded buffer/RAM growth or unexplained regression.

Half-duplex remains baseline. Full-duplex, barge-in, echo cancellation, wake-word and streaming are explicitly separate later candidates.