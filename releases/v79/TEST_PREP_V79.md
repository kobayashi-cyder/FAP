# V79 TEST PREP — bounded STT/TTS adapter evidence

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify V79 independently of V78 and all media sibling lanes; do not modify main.

## Deterministic gate
- Unit-test provider-neutral STT/TTS contracts, adapter translation, typed errors, evidence redaction and cleanup with fixed local fixtures and stable hashes.
- Reject malformed schema/JSON/base64/UTF-8, unsupported codec/MIME/sample-rate/channels, zero/truncated/oversized audio, empty/oversized transcript, invalid/oversized TTS text and metadata/hash mismatch.
- Missing provider/credential must fail closed with no transcription/synthesis claim.
- Inject timeout, DNS/transport error, HTTP non-2xx/provider error, wrong MIME, empty artifact/transcript and undecodable TTS bytes; retries remain off by default.
- Exercise request/response bytes, text length, audio duration and format limits at boundary and boundary+1; reject before unbounded allocation, retention or export.
- Fixtures are reproducible, bounded and credential/user-content free.

## Real-backend evidence gate
STT and TTS are separate claims. No real transcription/synthesis claim until the exact concrete adapter is independently exercised against its actual non-mocked backend. Evidence records adapter/provider identity, outcome, MIME/format, bounded input/output byte counts, duration where applicable, content hash and measured wall latency; capture peak RSS delta and retained-storage bytes where feasible, otherwise mark `unavailable`. Never retain credentials, source/synth text, transcript, provider payload or raw audio in evidence by default.

## Android/host audio gate
V79 does not own capture/playback. If Android/host microphone or speaker behavior enters this candidate, require RECORD_AUDIO/permission denial+revocation, microphone acquire/release and cancellation/interruption, audio-focus gain/loss, speaker/output acquire/release, background/foreground lifecycle, no raw-audio retention by default, and latency/RAM/battery measurements where feasible; otherwise split that behavior into its platform-lifecycle candidate before promotion.

## Privacy/resources
Assert raw input/output audio and transcripts are not retained after delivery/validation by default; temporary files are bounded and deleted on success, failure and cancellation; logging/telemetry excludes user audio/text and secrets. Repeated-call tests must detect RSS/storage growth and leaked handles/tasks.

## Regression gate
Run V77 focused image-adapter/evidence tests where shared boundaries are touched, current V69/V70 regressions, and applicable V66-V68 core suites. No skip/xfail/deletion may mask inherited failures. Compile/import checks and resource probes must pass in the supported CI matrix.

## Rollback/disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable/remove the concrete adapter while preserving provider-neutral contracts, on bounds/privacy bypass, lifecycle/resource leak, backend incompatibility, evidence mismatch or unexplained regression. If backend/credential/network/independent exercise is unavailable, DEFER the real STT/TTS claim.

Half-duplex remains the voice baseline. Full-duplex, barge-in, echo cancellation, wake-word and streaming require separate candidates and tests.