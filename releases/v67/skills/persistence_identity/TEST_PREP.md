# V67 Persistence + Identity Test Preparation

Baseline: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Material update
V67 now contains a shadow-table migration for `evidence`, `canary_obs`, and `failures`. The intended invariant is narrower than the original prototype: local `event_id` may repeat across capabilities, while `attestation_id` and holdout evidence SHA remain globally single-use.

## Required deterministic verification
1. Run `test_persistence_identity.py` and `test_migration_v67.py` from a clean checkout; do not inherit the earlier unexecuted PASS claim.
2. Build exact V66-shaped SQLite fixtures for production evidence, canary observations, quarantine failures, and quarantine releases. Record pre-migration schema SQL, row counts, and representative row hashes.
3. Prove migration is atomic: inject failure after each shadow copy/rename boundary and verify transaction rollback leaves the V66 schema/data intact.
4. Prove post-migration `(capability_id,event_id)` accepts the same local event/failure/observation ID across two capabilities but rejects a duplicate within one capability.
5. Prove `attestation_id` remains globally UNIQUE across capabilities and reused holdout `evidence_sha256` still cannot release quarantine twice.
6. Close/reopen after migration and after rollback; require identical row counts, preserved release cutoffs, quarantine status, canary stage/status, and EvidenceManifest/provenance references.
7. Run migration twice and require idempotence with no second backup/shadow mutation.
8. Run rollback after adding V67-only cross-capability duplicate local IDs. Rollback must fail safely or require an explicit preflight because V66 cannot represent those rows; never silently discard them.
9. Verify no foreign-key/index/trigger objects attached to the legacy tables are lost. If production schemas have any, fixtures must include them before KEEP.
10. Measure migration time and temporary disk amplification at representative DB sizes; record peak bytes and failure behavior under simulated disk-full/readonly conditions.

## Regression gates
- Existing V66 tests must remain green when run against untouched V66 fixtures.
- No evidence, quarantine, holdout, attestation, wrapper, or candidate digest may change value during migration.
- Global anti-reuse semantics for attestation and holdout evidence are non-negotiable.

## Acceptance
`KEEP` only after clean-runtime execution plus atomic-failure, restart, rollback-preflight, schema-object, and resource evidence. `MODIFY` if any migration invariant is unproven. `KILL/REPLACE` if capability-scoped event identity weakens cryptographic/provenance binding or cannot be migrated without silent loss.

Rollback anchor: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.