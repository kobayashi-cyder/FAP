# V80 TEST PREP — Android/host audio lifecycle

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify independently of V78/V79 and every media sibling lane; do not modify main.

## Deterministic gate
- Unit-test MicSource/AudioSink state machines, cancellation, bounded buffers and idempotent cleanup with deterministic host doubles/PCM fixtures.
- Reject malformed configuration, unsupported MIME/format/rate/channels, zero/partial/oversized frames, read/write before start/open, duplicate terminal calls, overflow/underflow and request/response size boundary+1.
- Provider/STT/TTS absence must not affect lifecycle behavior; no generation/transcription/synthesis claim exists in V80.
- Inject device/input/output error, timeout where host operations are bounded, cancellation at every state, focus denial/loss and cleanup exceptions.

## Android/host evidence
Require Android instrumentation for RECORD_AUDIO grant, denial, don't-ask-again and runtime revocation; prove no capture before grant and immediate stop/release after revocation. Exercise microphone start/stop/release, activity/service teardown, device loss and 100-cycle reuse. Playback must exercise focus acquire/loss/interruption/abandon plus speaker/output open/write/stop/release on success, cancellation and error. No background mic by default; session is explicit/user initiated.

## Privacy/resources
Assert raw audio is memory-only and not retained by default; no recording file, telemetry payload or transcript log. Verify temporary/buffer bytes are released on every terminal path. Measure startup/stop and playback latency, peak RSS delta, buffer high-water mark, retained storage (expected zero) and battery impact where feasible; mark unavailable metrics rather than estimate.

## Regression gate
Run current V69/V70 regressions and applicable V66-V68 core suites; also run V77 shared-boundary tests if touched. No skip/xfail/deletion may mask inherited failures. Compile/import checks and resource probes must pass in the supported matrix.

## Rollback/disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable platform capture/playback glue, on capture after denial/revocation, background capture, focus/sink/mic leak, non-idempotent cleanup, raw-audio retention, unbounded buffer/RAM growth or unexplained regression. DEFER Android KEEP if permission/focus/lifecycle cannot be independently exercised on device/emulator.

Half-duplex remains baseline. Full-duplex, barge-in, echo cancellation, wake-word and streaming require separate candidates and dedicated tests.