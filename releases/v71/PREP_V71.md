# PREP V71 — Replay divergence localization

Status: PREPARED, non-binding. Base main: `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68). V71 is independently prepared and MUST NOT be promoted ahead of unresolved V69/V70.

## Re-plan from current repository

Current main V68 provides bounded TaskPlan/AST repair and candidate-race mechanics. V69 is prepared as Android artifact provenance and V70 as deterministic replay observability. V71 should not widen code execution or duplicate either predecessor. The smallest useful follow-on is pure fault localization over two already-canonical replay traces: identify the earliest divergent event/state boundary and produce a bounded diagnostic record.

If V70 changes materially before promotion, re-evaluate this plan against its final replay schema. If no stable canonical replay trace exists, DEFER V71 rather than inventing an incompatible format.

## Smallest coherent experiment

Add a deterministic divergence locator that compares two canonical replay traces/envelopes without executing arbitrary code or Android actions.

Expected files remain under `releases/v71/`, for example:
- `fap_autonomy/replay_divergence.py`
- `tests/test_replay_divergence.py`
- deterministic fixtures and `RELEASE_REPORT_V71.md`.

Proposed interfaces:

`locate_first_divergence(expected, actual, policy) -> DivergenceResult`

`verify_divergence(result, expected, actual, policy) -> VerificationResult`

The result should contain only stable identifiers/digests, divergence index/category, schema/version information, and bounded redacted metadata required to reproduce the comparison. It must not silently copy full user/media payloads.

## Required behavior and negative tests

- identical traces return explicit `no_divergence`;
- single field mutation locates the first changed event deterministically;
- insertion/deletion/reordering are distinguished where schema permits;
- duplicate/malformed event identity fails closed;
- incompatible/unknown schema fails closed;
- malformed digest or truncated trace fails closed;
- policy/config mutation changes or invalidates the diagnostic digest;
- repeated fresh-process runs produce identical diagnostic serialization/digest;
- empty traces, one-sided empty trace and boundary-index cases are covered;
- absolute paths, wall-clock values, random values and secret/user payloads cannot leak into canonical diagnostic output;
- comparator exceptions/resource-limit failures are explicit failures, never PASS.

Fixtures must be tiny, reproducible and have documented expected digests. Synthetic traces are mechanism evidence only.

## Dependency boundary

V71 may consume a finalized V70 canonical replay envelope only through a narrow adapter. It must not copy V70 hashing/canonicalization logic. Until V70 is promoted, tests should use a local minimal protocol/fixture so V71 remains independently testable. After V70 promotion, rebase/re-plan and add compatibility tests before V71 promotion.

V69 provenance identifiers may be carried as opaque optional digests only; V71 must not implement artifact provenance itself.

## Android implications

No Android permission, service, receiver, applicationId/package, microphone/audio focus, storage broadening or background-execution change. Real-device divergence claims require a separately exercised concrete Android event adapter; synthetic fixtures do not establish device determinism.

## Privacy / retention / resources

Default diagnostic output must exclude raw text prompts, credentials/tokens, device identifiers, private absolute paths, microphone/audio, image/video bytes and other user payload bodies. Prefer stable hashes/redacted type metadata. Measure diagnostic size, comparison latency and peak memory for small and representative larger traces where feasible. Bound retained context around a divergence; avoid retaining entire traces solely for diagnostics.

## Promotion evidence

Require focused deterministic tests, malformed-input matrix, compile/static checks, current-main cumulative regression, fresh-process repeatability, privacy assertions, resource measurements and clean disable/removal. After V70 promotion, require explicit V70 compatibility evidence on the same candidate HEAD. Self-authored diagnostic output is not independent evidence that tests ran.

## Rollback

Additive only. Rollback is removal/disable of V71 divergence localization with no migration of V68/V69/V70 state. Record the actual implementation-base SHA as the rollback anchor when implementation starts.

## DEFER / REPLACE conditions

DEFER if V70 lacks a stable canonical trace/envelope, if localization requires executing candidate code/providers/device actions, or if privacy-safe bounded diagnostics cannot identify useful divergence. REPLACE if promoted V70 already includes independently tested first-divergence localization; in that case V71 should become a narrowly scoped compatibility/fault-injection experiment instead of duplicating it. KILL any design that treats heuristic similarity as deterministic equivalence or weakens fail-closed schema validation.
