# V67 Persistence + Identity Test Preparation

Baseline: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Independent observations from current main

Current V66 `ProductionCapabilityMatrix` uses global `event_id PRIMARY KEY` and global `attestation_id UNIQUE`. Current `StagedCanaryController` also uses global `canary_obs.event_id PRIMARY KEY`. Therefore cross-capability reuse of otherwise valid external IDs can collide before capability identity is considered.

## Required verification

1. Prototype unit tests: deterministic scoped identity, cross-capability same local event ID accepted, same-capability duplicate rejected, reopen persistence.
2. Legacy guard: do not alter any V61-V66 table in place in V67. Existing DB files must remain readable by existing code.
3. Migration experiment must be copy-on-write or shadow-table only until fixtures prove rollback.
4. Canary test must cover same `event_id` under two capability IDs and prove the current global-key behavior before proposing a migration.
5. Restart tests must close/reopen between canary stages and around quarantine release.
6. Holdout-use evidence must remain single-use after reopen.
7. Any DDL proposal needs a rollback anchor at main `d6329968...` and a byte-preserving backup/restore demonstration.

## Acceptance gate

KEEP the scoped-identity contract/prototype if its tests pass and the collision is reproducible against V66. MODIFY before integration because production tables cannot safely change until legacy migration/restart fixtures pass. KILL only if repository-wide evidence proves event/attestation IDs are intentionally globally unique and cryptographically bound to capability identity.
