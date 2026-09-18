# V81 PREP — bounded chat reliability

Base / rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (actual main, V77 KEEP). Independent of V78-V80 and media sibling branches.

## Candidate boundary
Small chat-only reliability candidate: bounded request/context construction, typed provider-neutral response/error envelope, cancellation/timeout, deterministic truncation and truthful capability reporting. No image/audio provider dependency and no voice-session expansion.

Expected interfaces/files: `ChatRequest`, `ChatResponse`, `ChatError`, context budget/truncator, provider-neutral chat adapter boundary, cancellation/timeout policy, redacted evidence metrics, focused fixtures/tests. Concrete chat providers remain replaceable behind the adapter and must not leak provider payloads into core interfaces.

## Negative tests
Empty/oversized input; malformed role/message structure; context exactly at and one over limits; invalid UTF-8/provider response; timeout/cancel/race; non-2xx/provider error; empty/oversized response; duplicate completion; retry disabled; secret-like metadata redaction; deterministic truncation under repeated identical fixtures. No silent fallback that changes provider or capability claims.

## Privacy / retention / resources
Conversation/provider payload logging off by default. Evidence records only bounded metadata: adapter identity, outcome, byte/token-like counts where locally measurable, wall latency, peak RSS delta and retained-storage bytes. Do not store message text, credentials or raw provider payload by default. Unsupported metrics are `unavailable`, not estimates. Context buffers released after request completion unless caller explicitly owns history.

## Android implications
No microphone, RECORD_AUDIO permission, audio focus or speaker lifecycle in V81. Text chat must remain usable without any media permission. Android UI integration, if touched, must preserve cancellation on lifecycle teardown and bounded memory.

## Promotion evidence
Focused deterministic/negative tests, cancellation and resource-leak repetition, compile/import checks, applicable V69/V70 and core regressions. Any concrete provider claim additionally requires an independent non-mocked backend exercise; provider-neutral reliability can KEEP without such a claim.

## DEFER / REPLACE
DEFER provider-specific capability when backend/credential/network evidence is unavailable. REPLACE/split any image/audio/lifecycle behavior that enters this candidate. Roll back on privacy leak, nondeterministic truncation, unbounded context/RAM growth, cancellation leak, misleading capability reporting or unexplained regression.

Half-duplex remains unchanged. Full-duplex, barge-in, echo cancellation, wake-word and streaming remain separate later capabilities.