# FAP V67 Preparation Context

## Inherited state

- Inherited main SHA: `d6329968a579fa0d20dbdb115a6f7a060d13a68e`
- Parent main SHA: `ee72c1068c643172118f6afdf7bd90e7efe29d16`
- Latest completed release on main: `v66`
- Work branch: `listener/v67`
- Rollback anchor: `d6329968a579fa0d20dbdb115a6f7a060d13a68e` (do not modify main; abandon/recreate listener work from this SHA if V67 preparation regresses)

## Changed surfaces inherited from V66

V66 adds authenticated production evidence and a statistical canary repair loop. The main surfaces are:

- `attestation.py`: trusted-wrapper HMAC execution attestation.
- `telemetry_v66.py`: authenticated production telemetry.
- `production_matrix.py`: deduplicated verified production evidence.
- `statistical_canary.py`: stage-isolated statistical rollout decisions.
- `quarantine_release.py`: verified untouched-holdout release gate.
- `repair_bridge.py`: rollback/quarantine to non-executable repair requests.
- `v66_coordinator.py`: integration path across verification, canary, quarantine, repair and capability evidence.
- `tests/test_v66_operational.py`: V66 control-path coverage.
- Android remains on the existing schema-1/schema-2 state-sync adapters; V66 did not introduce a new Android state schema.

## Interfaces that must remain compatible

1. Existing V61-V65 `fap_autonomy` imports and public coordinator behavior.
2. SQLite state created by the V64/V65 canary and quarantine ledgers.
3. `AndroidStateSync` schema 1 readers and `AndroidV65StateSync` schema 2 readers.
4. Candidate digest, capability ID and family identity semantics across activation, canary, quarantine and production evidence.
5. Holdout evidence must remain single-use for quarantine release.
6. The attestation key and telemetry key remain separate trust domains; candidate code must not receive either key.
7. V66's documented 5% -> 20% -> 50% -> 100% rollout sequence and stage-isolation behavior.

## Likely V67 implementation targets

Priority is hardening state/evidence identity and restart behavior before adding broader autonomy:

1. Verify every SQLite uniqueness key is scoped by the full semantic identity (`capability_id`, candidate/family where applicable, event/evidence identity). In particular, test cross-capability reuse/collision behavior rather than assuming globally unique external IDs.
2. Add restart/reopen tests proving stage evidence, quarantine cutoffs and release evidence cannot be confused after process restart.
3. Add schema/version inspection and migration tests for persisted SQLite databases before any schema mutation is attempted.
4. Define bounded retention/compaction for append-only production telemetry and operational evidence without deleting evidence required for rollback/audit.
5. Extend Android export only additively. If V66 production status is exposed, introduce schema 3 rather than silently changing schema 2; keep schema 1/2 writers intact.
6. Bind APK/package metadata to source main SHA, release manifest and verification result so an installed artifact can identify the exact evidence-bearing release.

## Regression hazards

- A global `UNIQUE`/primary-key assumption can reject valid evidence from another capability or, worse, alias evidence identities.
- Resetting canary evidence after quarantine release must not resurrect stale observations after reopening the DB.
- Statistical decisions must remain stage-isolated; carrying 5% observations into 20%/50% changes the intended confidence accounting.
- Schema changes without explicit migration can make existing Android/runtime state unreadable.
- Retention must not remove the evidence needed to justify quarantine, rollback or holdout non-reuse.
- HMAC authentication is symmetric host-wrapper authentication, not hardware/remote attestation; V67 must not widen that claim.

## Packaging / Android implications

- Current Android writers already use temp-file + `fsync` + `os.replace`, so atomic replacement should be preserved.
- Schema 2 currently exports active/canary/quarantine state only. V66 production evidence should not be inserted into schema 2 with changed semantics.
- APK metadata should include source main SHA and release version already used by the Android build pipeline; V67 should add verifiable manifest/evidence linkage rather than a second independent version source.

## Required verification before promotion

- Run V66 delta tests and cumulative V65+V66 regression unchanged.
- Add cross-capability identity collision tests.
- Add close/reopen/restart persistence tests for canary/quarantine/release state.
- Add old-database compatibility tests before any SQLite DDL change.
- Run `compileall` and warnings-as-errors.
- Run synthetic healthy rollout and rollback/quarantine/repair/release cycles after restart.
- Verify Android schema 1 and 2 output remains byte/field compatible for existing consumers.
- If schema 3 is added later, test simultaneous generation/reading of legacy schemas.

## V66-V1000 planning position

The next experiment should be **V67: Persistence + Identity Hardening**, not another large autonomy feature. V66 substantially widened the trusted operational surface; the highest-value next step is proving that evidence identity, restart persistence, schema compatibility and artifact provenance remain correct under long-running operation. After that, V68 can reasonably target bounded evidence retention/compaction and V69 can target Android schema-3 observability/artifact attestation linkage. Later roadmap versions should remain evidence-driven rather than pre-allocating functionality through V1000; version numbers are planning slots, not proof of completed capability.
