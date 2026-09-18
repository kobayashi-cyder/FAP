# V82 PREP — bounded half-duplex voice-session orchestration

Base / rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (actual current main, V77 KEEP). V82 is independent of V78-V81 and all media sibling branches; it must compile/test with unavailable STT/TTS and platform audio adapters.

## Candidate boundary
Small provider-neutral half-duplex session coordinator only: explicit states `IDLE -> CAPTURING -> TRANSCRIBING -> THINKING -> SYNTHESIZING -> PLAYING -> IDLE`, cancellation, bounded handoff envelopes, and truthful capability gating. No concrete STT/TTS/image backend is added here and no generation/transcription/synthesis claim follows from this candidate alone.

Expected files/interfaces: `VoiceSession`, `VoiceState`, `VoiceCapabilities`, bounded `CapturedAudioRef`, `TranscriptRef`, `ChatTurnRef`, `SynthAudioRef`, cancellation/deadline policy, adapter ports for mic source/STT/chat/TTS/audio sink, redacted session metrics, deterministic fake adapters and focused tests. Provider/renderer/platform payloads remain behind their ports; the coordinator accepts only bounded neutral envelopes and never imports provider SDK schemas.

## Negative tests
Missing/disabled capability at every port; start while non-IDLE; cancel/timeout at every state; STT/TTS/chat/provider error; mic/output lifecycle error; zero/oversized audio or text handoff; duplicate callback/completion; stale callback after cancellation; illegal state transition; adapter exception; activity/session teardown; repeated 100-cycle success/failure/cancel runs. Fail closed to terminal cleanup; never silently substitute a provider or claim a capability that lacks independent evidence.

## Android / host implications
V82 does not request `RECORD_AUDIO` or own Android audio focus directly. When a platform adapter is supplied, capture may begin only after its explicit permission-granted signal; permission revocation/device loss cancels the session. Playback may begin only after output focus/open succeeds; focus loss stops playback and terminal cleanup abandons/releases through the platform port. No background mic by default. Lifecycle teardown must cancel and release all owned handles. V80-style platform behavior remains separately promotable evidence, not assumed by V82.

## Privacy / retention defaults
Raw audio, transcript, chat text and synthesized audio logging off by default; telemetry off by default. Session coordinator retains only bounded in-memory references for the active turn and drops them on terminal cleanup unless the caller explicitly owns history/export. Evidence stores state/outcome, adapter identities/capability flags, byte/count/duration metrics, latency and resource measurements only—no credentials, prompt/transcript text, provider payload or raw audio.

## Resource metrics
Promotion evidence records end-to-end and per-state wall latency, peak RSS delta where measurable, handoff buffer high-water bytes, and retained-storage bytes (expected zero without explicit export). Repeated-cycle evidence checks RAM/handle growth. Unsupported metrics are `unavailable`, never estimated.

## Promotion evidence
Deterministic state/negative tests; cancellation and stale-callback tests; 100-cycle resource/cleanup test; compile/import checks; applicable core regressions. KEEP only the orchestration claim without real backends. Any claim that a turn actually transcribes, chats, synthesizes or plays requires independent evidence for each concrete adapter involved plus platform lifecycle evidence where applicable. Missing evidence keeps that capability disabled/DEFERRED.

## DEFER / REPLACE
DEFER real voice-turn claims while any required concrete STT/TTS/chat/platform adapter lacks independent evidence. REPLACE/split if the coordinator must understand provider schemas, own Android permission/focus policy, retain raw media/text by default, or introduce unbounded buffers. Roll back on privacy leak, illegal transition, stale callback mutation, cleanup/focus/mic leak, unbounded RAM/storage growth or unexplained regression.

Full-duplex, barge-in, echo cancellation, wake-word and streaming are explicitly out of scope and remain separate later capabilities.
