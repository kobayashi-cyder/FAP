# V67 Decision

Decision: **KEEP**

Baseline main: `d6329968a579fa0d20dbdb115a6f7a060d13a68e` (V66)

## Retained implementation

- capability-scoped deterministic identity for local event IDs
- composite `(capability_id, event_id)` uniqueness for production evidence, canary observations, and quarantine failures
- globally single-use `attestation_id` retained
- globally single-use holdout `evidence_sha256` retained
- copy-on-write/shadow-table migration from the representative V66 SQLite schema
- preserved backup tables for explicit rollback
- idempotent restart/reopen behavior
- rollback restoring the V66 global-event-ID constraints

## Independent evidence

GitHub Actions run `35285921275` at candidate SHA `c60f6a7acd0542125ed9b2d6d035b679026e8f44` completed successfully on both Python 3.11 and 3.12.

Each matrix job independently completed:

- compile V67 skill: PASS
- V67 skill tests: PASS
- V66 operational regression: PASS

The checked-in migration tests cover row preservation, same local event ID across different capabilities, global attestation single-use, global holdout-evidence single-use, idempotent restart with backups, and rollback restoring V66 identity behavior.

## Promotion recommendation

V67 is eligible for integration review. Integration should transplant only the coherent V67 persistence-identity delta and its tests/evidence; unrelated V68+ or media experiments remain outside this decision.

## Rollback anchor

Until promotion, rollback is abandonment of this branch to V66 main SHA `d6329968a579fa0d20dbdb115a6f7a060d13a68e`. After promotion, the migration's retained V66 backup tables provide the schema rollback path tested by `rollback_v67_identity_schema`.

## Limitations

The legacy fixture is a representative reconstruction of the persisted V66 tables used by this migration, not a byte-for-byte snapshot of every historical V61-V66 database ever produced. Real deployed databases should still be backed up before first migration. This decision does not approve V68+, media skills, or any change to attestation/holdout global replay protection.
