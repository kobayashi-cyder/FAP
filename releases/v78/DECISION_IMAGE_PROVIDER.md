# V78 decision — image provider evidence gate

Decision: **DEFER real generation / MODIFY candidate pending independent verification**.

Rollback anchor: main V77 `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`.

This candidate adds only provider-neutral, privacy-safe evidence plumbing and deterministic bounds/privacy tests. It deliberately does not add or claim a real image provider because no live provider credential/backend was independently exercised in this run. Evidence contains provider/adapter identity, validated MIME/dimensions, byte count/SHA-256, measured latency, optional measured RSS delta, and retained-storage count; prompt text, credentials and raw image bytes are excluded.

Promotion requires independent CI on the exact candidate HEAD plus a separate real-backend run before any real-generation KEEP claim. Roll back to the anchor, or remove `releases/v78`, if evidence leaks sensitive/raw content, validation can be bypassed, allocations become unbounded, or inherited regressions appear.

Limitations: no real backend invocation; no image-quality claim; no Android network/decode integration; RSS is nullable when unavailable. Audio, full-duplex, barge-in, echo cancellation, wake-word and streaming are out of scope.
