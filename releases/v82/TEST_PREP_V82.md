# V82 TEST PREP — bounded half-duplex voice-session orchestration

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify V82 independently of V78-V81 and every media sibling lane; do not modify main.

## Deterministic gate
- Unit-test every legal state transition `IDLE -> CAPTURING -> TRANSCRIBING -> THINKING -> SYNTHESIZING -> PLAYING -> IDLE`, terminal cleanup, deadlines and idempotent cancellation with deterministic fake ports and stable fixtures.
- Reject malformed envelopes, invalid state/order, zero/oversized audio, empty/oversized transcript/chat/TTS handoffs, invalid UTF-8, duplicate completion and stale callback after cancellation.
- Missing/disabled mic, STT, chat, TTS or output provider must fail closed with truthful unavailable capability; never substitute providers or claim transcription/synthesis/playback.
- Inject provider timeout/error/exception, wrong MIME, empty artifact/transcript, mic/output failure, focus loss and cancellation at every state. Enforce request/response/handoff byte and duration limits at boundary and boundary+1.
- Fixtures are local, reproducible, bounded and contain no credential or user content.

## Concrete-adapter evidence gate
No real transcription, chat, synthesis or playback claim follows from orchestration tests. Each concrete STT/TTS/chat/platform adapter must be independently exercised against its actual non-mocked backend/device before the corresponding real capability claim. Evidence records adapter/provider identity, outcome, MIME/format, bounded byte/count/duration metrics, hashes where appropriate and measured latency; capture peak RSS delta and retained-storage bytes where feasible, otherwise `unavailable`. Evidence excludes credentials, prompts/transcripts/provider payloads and raw audio.

## Android/host audio gate
Where platform audio is supplied, require RECORD_AUDIO grant/denial/revocation, no capture before grant, mic acquire/start/stop/release, activity/session teardown, device loss, audio-focus acquire/loss/abandon, interruption/cancellation, and speaker/output open/write/stop/release on success/error/cancel. No background mic and no raw-audio retention by default. Measure capture/playback/session latency, peak RAM, buffer high-water mark, retained storage and battery impact where feasible.

## Privacy/resources
Raw audio, transcript, chat text and synthesized audio logging/telemetry are off by default. Assert active-turn references and temporary bytes are dropped on every terminal path unless explicitly caller-owned. Run 100-cycle success/failure/cancel tests for RSS/storage/handle/task growth.

## Regression gate
Run current V69/V70 regressions plus applicable V66-V68 core suites; run later shared-boundary regressions only when touched. No skip/xfail/deletion may mask inherited failures. Compile/import and resource probes must pass in the supported matrix.

## Rollback/disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable the affected port/capability, on illegal/stale transition mutation, bounds/privacy bypass, mic/focus/output leak, raw-media retention, unbounded RAM/storage growth, misleading capability reporting or unexplained regression. Missing independent adapter evidence keeps that capability disabled/DEFERRED.

Half-duplex is the only V82 voice baseline. Full-duplex, barge-in, echo cancellation, wake-word and streaming require separate candidates and dedicated tests.