# PREP V70 — Deterministic replay observability

Status: PREPARED, non-binding. Base main: `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68). V70 is prepared independently; implementation must not be promoted ahead of unresolved V69.

## Re-plan from current repository

The existing `skill/v70-deterministic-replay` experiment diverged from the V66-era base and is 17 main commits behind current V68. Do not merge it wholesale. Treat its small replay modules/tests as advisory candidates for selective transplantation only after reconciling V68 TaskPlan/candidate-race evidence shapes and, if V69 is promoted, its artifact provenance identifiers.

## Smallest coherent experiment

Add a pure deterministic replay envelope and verifier for already-recorded FAP decision/evidence events. The experiment must prove that the same canonical input sequence and explicit configuration produce the same canonical replay digest/result, while any mutation, reordering, omission, duplicate identity, incompatible schema, or undeclared nondeterministic field fails closed or is explicitly excluded by schema.

Expected files stay under `releases/v70/`, for example `fap_autonomy/deterministic_replay.py`, focused tests, fixtures, and a release report. No Android UI/runtime behavior changes.

## Interfaces / boundaries

`canonicalize_replay(events, config) -> ReplayEnvelope`

`verify_replay(envelope, events, config) -> ReplayVerification`

`run_replay(events, reducer, config) -> ReplayResult`

Canonical serialization must specify field ordering, encoding, integer/time representation and treatment of optional fields. The reducer boundary must be injected; replay infrastructure must not execute arbitrary candidate code, shell commands, network calls, providers, or Android actions.

If V69 provenance is available, V70 may reference its immutable artifact/source digest but must not duplicate provenance logic. If V69 is not promoted, keep the field optional and do not create an incompatible predecessor dependency.

## Required negative tests

- one-byte/event-field mutation;
- event reordering, omission and duplication;
- malformed/duplicate event identity;
- unknown/incompatible schema version;
- config mutation and omitted required config;
- wall-clock/random/absolute-path leakage into canonical output;
- malformed digest and replay-result mismatch;
- restart/cross-process repeatability;
- reducer exception/timeout represented as explicit failure, never PASS.

Use small committed/generated fixtures with documented digests. Do not claim production determinism from synthetic fixtures alone.

## Resource / privacy constraints

Measure serialized envelope size, replay latency and peak memory for small and representative larger sequences where feasible. Prefer streaming/incremental hashing when possible. Replay evidence must contain only the minimum event/config fields required for reproduction; exclude user content, credentials/tokens, microphone/audio/image/video payloads, device identifiers and private absolute paths unless a later reviewed schema explicitly requires redacted equivalents.

## Android implications

No new Android permission, service, receiver, applicationId/package change, microphone/audio focus, storage broadening, or background execution is allowed in this slice. Android-origin events may be fixtures, but a real-device replay claim requires separate concrete adapter evidence.

## Promotion evidence

Require deterministic focused tests, malformed-input matrix, compile/static checks, current-main cumulative regression, repeated fresh-process replay with identical digest, resource measurements, privacy assertions, and a clean disable/removal check. Evidence authored by the replay itself is not independent proof that external tests ran.

## Rollback

V70 must be additive and removable without migration of V68 state. Rollback anchor is the main SHA from which the implementation branch is created; if V69 is promoted first, rebase/re-plan and record that new anchor before implementation verification.

## DEFER / REPLACE conditions

DEFER production/Android determinism claims until concrete event adapters are independently exercised. DEFER replay of arbitrary generated code, network/provider calls, media bytes, full device state, and timing-sensitive concurrency. REPLACE this plan if current main or promoted V69 already provides an equivalent canonical replay verifier with stronger independent tests; then V70 should become a compatibility/fault-injection experiment rather than duplicate it.

## Existing skill branch

`skill/v70-deterministic-replay` contains a useful prototype but is stale relative to V68. Reuse only individually reviewed files/ideas; preserve branch isolation and do not merge its V66 ancestry.
