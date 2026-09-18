# TEST PREP V70 — Deterministic replay observability

Status: PREPARED, non-binding. Verification base: main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68). V70 remains independently testable and must not be promoted ahead of unresolved V69.

## Scope
Verify only the additive replay envelope/canonicalizer/verifier/reducer boundary in PREP_V70. Do not merge the stale `skill/v70-deterministic-replay` branch wholesale. If V69 is promoted before V70 implementation, refresh the rollback anchor and verify any provenance reference without duplicating V69 logic.

## Deterministic unit tests
- identical ordered events + identical explicit config produce byte-identical canonical serialization, replay digest and result across repeated runs and fresh processes;
- canonical field ordering, UTF-8 encoding, integer/time representation and optional-field treatment are pinned by fixtures;
- reducer is injected and receives only declared canonical inputs;
- equivalent supported input construction order does not change canonical bytes;
- deterministic fixtures have documented SHA-256 values.

## Malformed / fail-closed matrix
Reject or explicitly fail: one-byte/event-field mutation; reorder; omission; duplicate event; malformed/duplicate identity; unknown/incompatible schema; missing or mutated required config; malformed digest; replay-result mismatch; invalid encoding/type; undeclared nondeterministic field. Wall-clock, random values, private absolute paths and process-specific values must not silently enter canonical output. Reducer exception, cancellation or timeout is an explicit failure, never PASS.

## Isolation / provider boundary
Replay infrastructure must not execute arbitrary candidate code, shell commands, network calls, media providers/renderers, Android actions or hidden filesystem reads. Tests use a fake deterministic reducer plus failure/timeout reducers. Any future external/provider replay requires a separate adapter and independent evidence; synthetic replay is not evidence of production determinism.

## Regression / compatibility
Run focused V70 tests, compile/static checks and the current-main cumulative V68 suite from the same candidate HEAD. If V69 has been promoted, also run V69 regression and verify V70 only references immutable provenance identifiers. Existing V68 TaskPlan/candidate-race evidence must remain unchanged. No Android applicationId/package/schema mutation is allowed.

## Reproducibility / resource metrics
Run at least two fresh-process repetitions and compare canonical bytes/digests. Measure envelope bytes, replay wall time and peak memory for a tiny fixture and a representative larger event sequence. Prefer incremental/streaming hashing; whole-history buffering that causes unacceptable linear peak-memory growth is MODIFY. Record Python/OS/tool versions with measurements.

## Privacy / retention assertions
Replay evidence contains only minimum declared event/config fields. Tests must assert absence of user content, credentials/tokens, raw microphone/audio/image/video payloads, device identifiers and private absolute paths. No new retention policy is implied by replay; disable/removal must not strand new persistent state.

## Android implications
Assert no new Android permission, service, receiver, broad storage access, microphone/audio-focus behavior, background execution, applicationId or package change. Android-origin events may be synthetic fixtures only. A real-device determinism claim requires a separately exercised concrete event adapter.

## Independent evidence / promotion gate
KEEP only when focused deterministic tests, malformed-input matrix, fresh-process equality, compile/static checks, current-main cumulative regression, resource measurements, privacy assertions and rollback/removal checks pass on the same candidate HEAD with independently rerunnable commands/results. Replay-authored evidence alone does not prove those tests ran.

## Rollback / decisions
Rollback anchor is the implementation branch's actual main base. Clean disable/removal must restore predecessor behavior without migration. MODIFY for bounded determinism/resource defects; DEFER production/Android/provider determinism without concrete adapter evidence; REPLACE if predecessor already supplies equivalent stronger replay verification; KILL if replay requires arbitrary execution, hidden I/O, invasive schema changes, or cannot fail closed.

Highest-risk untested assumption: V68 event/evidence shapes may contain nondeterministic or insufficiently canonicalized fields, and a future V69 provenance identifier may alter the replay envelope contract. Both must be reconciled against the implementation HEAD before promotion.