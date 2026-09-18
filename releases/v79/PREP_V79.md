# V79 PREP — bounded STT/TTS adapter evidence

Base / rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (actual main, V77 KEEP). V79 is independent of V78 and all media sibling branches.

## Candidate boundary
Small candidate only: concrete STT and/or TTS provider adapters if a real backend can be independently exercised. Otherwise implement only provider-neutral contracts/evidence plumbing and explicitly DEFER transcription/synthesis claims.

Expected interfaces/files: provider-neutral `AudioInput`, `TranscriptResult`, `SpeechRequest`, `AudioOutput`, typed provider errors, bounded adapter configuration, evidence record/redactor, focused adapter tests and local fixtures. Concrete provider modules must remain behind those interfaces; provider SDK/HTTP payloads must not leak into caller contracts.

## Negative tests and bounds
Reject malformed schema/JSON/base64/UTF-8; unsupported codec/MIME/sample rate/channel count; zero/truncated/oversized audio; empty/oversized transcript; invalid TTS text; missing credential/provider; non-HTTPS credential transport; timeout/DNS/transport/non-2xx/provider errors; wrong MIME; undecodable TTS bytes; metadata/hash mismatch. Exercise request/response bytes, text length, duration and format limits at boundary and boundary+1. Retries off by default; fail closed before unbounded allocation or retention.

## Independent real-backend evidence
STT and TTS are separate claims. KEEP a real claim only after the exact concrete adapter runs against its actual non-mocked backend. Record provider/adapter identity, outcome, format/MIME, bounded input/output byte counts, duration when applicable, content hash, measured wall latency, peak RSS delta and retained-storage bytes when measurable. Mark unsupported metrics `unavailable`; never estimate. No credential, source/synth text, transcript, provider payload or raw audio in evidence by default.

## Android / host implications
V79 consumes caller-supplied bounded audio and returns bounded artifacts/text. It does not own microphone capture, Android RECORD_AUDIO permission, audio focus, speaker routing or output lifecycle. Those belong to the next platform-lifecycle candidate. If any such behavior enters V79, REPLACE/split it before promotion.

## Privacy / retention / resources
Raw input/output audio and transcript retention default to zero after the caller receives/validates the result; telemetry and prompt/transcript logging off by default. Temporary files must be scoped, bounded and deleted on success, failure and cancellation. Measure latency, peak RSS delta and retained storage on independent evidence runs; add repeated-call resource checks for leaks.

## Promotion evidence
Focused unit/negative tests; deterministic fixture hashes; compile/import checks; applicable V69/V70 and V66-V68 regressions; independent backend evidence for each claimed real adapter. No skip/xfail/test deletion may hide inherited failure.

## DEFER / REPLACE
DEFER real STT/TTS when backend, credential, network access or independent exercise is unavailable. Provider-neutral plumbing may still proceed without capability claims. REPLACE or disable an adapter on privacy leak, bounds bypass, unbounded resource growth, backend incompatibility or unexplained regression. Roll back to the anchor above.

Half-duplex remains the voice baseline. Full-duplex, barge-in, echo cancellation, wake-word and streaming remain separate later capabilities.