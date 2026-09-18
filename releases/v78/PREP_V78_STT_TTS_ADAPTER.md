# V78 candidate — provider-neutral STT/TTS adapter boundary

Base / rollback anchor: actual `main` commit `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). V69/V70 are already integrated and are not reprepared.

## Goal
Prepare the smallest independent speech adapter contract after V77. No real STT/TTS backend is available to this preparation run, therefore real transcription and synthesis are explicitly **DEFERRED**.

## Expected files / interfaces
- `releases/v78/speech/contracts.py`: `SpeechToTextProvider.transcribe(AudioInput)->TranscriptResult`; `TextToSpeechProvider.synthesize(SynthesisRequest)->AudioOutput`.
- `releases/v78/speech/limits.py`: bounded input bytes/duration, text length, timeout and output bytes.
- `releases/v78/speech/errors.py`: typed unavailable/timeout/invalid-input/invalid-output errors with no secret or media payload in messages.
- `releases/v78/speech/null_provider.py`: fail-closed provider used when no backend is configured.
- `releases/v78/tests/test_speech_contracts.py`: deterministic contract/negative tests.
- `releases/v78/metrics_schema.json`: wall latency, peak RSS delta, input/output bytes and temporary-storage bytes only.

## Provider boundary
FAP core owns normalized requests/results, limits, privacy policy and metrics. A provider adapter alone owns provider authentication, wire format, model/voice identifiers and response decoding. No provider SDK/type may cross the boundary. Renderer/playback and microphone capture are deliberately outside V78 and belong to later platform-lifecycle candidates.

## Negative tests
Reject empty/oversize audio, unsupported sample metadata, overlong synthesis text, malformed provider output, output above byte cap, timeout, missing provider, and provider exceptions. Verify fail-closed behavior and verify errors/metrics contain neither audio bytes, transcript text, synthesis text nor credentials.

## Privacy / retention defaults
No audio, transcript, synthesis text or synthesized audio is persisted or logged by default. No telemetry and no retry by default. Temporary material, if a later adapter requires it, must be opt-in, uniquely scoped, permission-restricted and deleted on success, failure and cancellation. Credentials must come from runtime configuration and must never be committed.

## Metrics / budgets to record before promotion
Record cold/warm wall latency, process peak RSS delta, request/response byte counts and temporary-storage peak. This PREP sets no invented performance numbers; promotion requires measured values from the candidate environment plus test fixtures and commands sufficient to reproduce them.

## Promotion evidence
Promotion requires: contract + negative tests passing; compile/static checks applicable to the implementation; regression checks against current main; an independently runnable evidence artifact showing a real STT and/or TTS adapter only if capability is claimed; measured RAM/latency/storage report; and proof that logs/errors do not retain media/text/secrets. Without independent real-backend evidence, promotion wording must remain provider-neutral and must not claim transcription/synthesis.

## Android permissions / audio focus / microphone lifecycle
V78 requests **no Android microphone permission** and does not acquire audio focus, open `AudioRecord`, start playback, or manage host devices. Those are platform lifecycle concerns reserved for the next independent candidate. This separation prevents a provider contract from silently acquiring hardware or permissions.

## Explicitly deferred
Real transcription, real synthesis, microphone capture, speaker playback, full-duplex, barge-in, echo cancellation, wake-word and streaming are DEFERRED. The latter five remain separate later capabilities.

## DEFER / REPLACE conditions
DEFER provider-specific code until a backend can be exercised with independent evidence. REPLACE an adapter if it leaks provider types across the boundary, requires persistent media by default, cannot enforce bounds/cancellation, or cannot provide reproducible evidence. Do not weaken the neutral contract merely to fit one provider.

## Branch discipline
This candidate lives only on `prep/v78-stt-tts-adapter`. Do not merge sibling media branches automatically. V78 is independently reviewable and rollback is the exact main anchor above.
