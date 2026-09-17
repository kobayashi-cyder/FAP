# V67 Decision

Decision: **MODIFY**

## Evidence

- The V67 prototype defines capability-scoped deterministic identity and a composite `(capability_id, event_id)` evidence key.
- Its checked-in unit suite covers deterministic scoping, same local ID across capabilities, duplicate rejection inside one capability, and close/reopen persistence.
- Current V66 production code still has global uniqueness constraints: `ProductionCapabilityMatrix.evidence.event_id` is the primary key, `attestation_id` is globally unique, and `StagedCanaryController.canary_obs.event_id` is globally primary-keyed. This establishes a concrete collision surface when an upstream/local identifier is only capability-scoped.

## Why not KEEP for integration yet

Changing existing persisted V66 tables without legacy fixtures could make deployed SQLite state incompatible. Restart/quarantine/holdout invariants also need explicit fixtures before DDL is touched.

## Safe retained result

Keep the prototype and scoped-identity contract on this non-main branch as the migration target. Do not promote schema changes yet.

## Required modification

Add legacy V61-V66 database fixtures, reproduce the cross-capability collision against current controllers, design a copy-on-write/shadow-table migration, and prove rollback plus restart invariants.

## Rollback

No main change occurred. Rollback is simply abandoning this branch and returning to `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Limitations

This run did not execute repository tests in a checked-out runtime; test status is therefore recorded as **not independently executed in this run**, not PASS. The decision relies only on code inspection and previously checked-in prototype structure.
