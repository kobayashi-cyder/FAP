# V83 PREP — bounded practical chat-turn capability

Base / rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (actual current main, V77 KEEP). V83 is independent of V78-V82 and every media sibling branch. Roadmaps are advisory only.

## Candidate boundary
Small provider-neutral bounded chat-turn layer: deterministic request envelope, bounded recent-turn context, explicit capability/unavailable result, cancellation/deadline, and redacted metrics. No model/provider capability is claimed unless a concrete chat adapter has independent evidence. V83 does not add image/STT/TTS/audio behavior.

Expected files/interfaces: `ChatTurnRequest`, `ChatTurnResult`, `ChatAdapter`, `ChatCapabilities`, `ChatContextPolicy`, `ChatDeadlinePolicy`, bounded message/content refs, deterministic fake adapter, focused unit tests, and a resource-evidence fixture. Provider SDK schemas remain strictly behind `ChatAdapter`; core chat code receives only neutral bounded envelopes.

## Negative tests
Unavailable/disabled adapter; empty input; oversized input/context/output; malformed role/order; deadline before dispatch; timeout during call; cancellation before/during/after completion; duplicate completion; stale callback after cancel; adapter exception; invalid UTF-8/provider payload conversion; 100-cycle success/failure/cancel repetition. Fail closed without silently selecting another provider or retaining content.

## Android / host implications
No new Android permission. No microphone, audio focus, playback, background service, wake lock or media ownership. Host lifecycle cancellation must invalidate outstanding callbacks and release adapter-owned handles. Any UI integration remains outside this candidate.

## Privacy / retention defaults
Prompt, response and conversation persistence off by default. Raw text/provider payload logging off; telemetry off. Only bounded in-memory turn/context refs survive during the active call and are dropped on completion/cancel unless the caller explicitly owns history/export. Evidence may retain adapter identity/capability flags, byte/token/count bounds where available, outcome and timing/resource measurements, never credentials or message text.

## Resource metrics
Promotion evidence records request/context/output byte high-water marks, end-to-end and adapter wall latency, peak RSS delta where measurable, retained-storage bytes (expected zero absent explicit export), and handle/RAM growth over 100 cycles. Unsupported metrics are `unavailable`, not estimated.

## Promotion evidence
Deterministic fake-adapter contract/negative tests, cancellation/stale-callback tests, bound enforcement, 100-cycle cleanup/resource evidence, compile/import checks and applicable core regressions. A real-chat claim additionally requires independent evidence from the exact concrete adapter/backend; otherwise promotion is only the provider-neutral chat boundary.

## DEFER / REPLACE
DEFER real chat/model-quality claims until a concrete adapter/backend has independent evidence. REPLACE or split if provider schemas leak into core, context becomes unbounded, content is retained/logged by default, Android media permissions become necessary, or deterministic cancellation cannot be maintained. Roll back to the base anchor on privacy leak, stale callback mutation, resource growth, bound bypass or unexplained regression.

Full-duplex, barge-in, echo cancellation, wake-word and streaming remain separate later capabilities.