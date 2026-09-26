# V67 Skill Lane — Persistence + Identity Hardening

Base: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Goal
Prove that evidence/event identities are scoped by semantic capability identity and survive process restart without accidental aliasing.

## Prototype
- `persistence_identity.py`
- capability-scoped deterministic identity helper
- SQLite ledger using composite `(capability_id, event_id)` primary key
- `(capability_id, attestation_id)` uniqueness
- explicit schema-version guard

## Verified locally
- 3/3 unit tests PASS:
  - same local ID across different capabilities does not collide
  - duplicate identity inside one capability is rejected
  - close/reopen preserves schema and rows

## Integration preparation
Before any main merge, compare this prototype against `production_matrix.py`, `operational_ledger.py`, canary/quarantine ledgers, and all existing persisted SQLite files. Do not mutate existing tables in place until migration tests exist.

Required next tests:
1. legacy V61-V66 DB fixture opens without mutation;
2. staged canary and quarantine restart cycle;
3. stale-stage evidence remains rejected after reopen;
4. holdout-use ledger remains single-use after restart;
5. rollback from a failed migration.

Decision gate: KEEP only if scoped identity fixes a real collision risk without breaking legacy DBs. Otherwise MODIFY or KILL.
