# V67 Integration Prep

Status: **BLOCKED / MODIFY**

Baseline main: `d6329968a579fa0d20dbdb115a6f7a060d13a68e` (V66)
Candidate branch: `skill/v67-persistence-identity`

## Integration decision

Do **not** promote V67 to main yet. The candidate correctly identifies a real capability-scoped identity/collision problem, but it is currently an isolated prototype under `releases/v67/skills/persistence_identity/` and does not safely migrate the persisted V66 production controllers.

## Blocking conditions

1. Add representative legacy SQLite fixtures covering V61-V66 persisted schemas/state.
2. Reproduce the cross-capability local-ID collision against the current production controllers, not only the prototype store.
3. Implement a copy-on-write or shadow-table migration that preserves existing evidence, attestation, quarantine/staging, and holdout state.
4. Prove restart/reopen invariants after migration.
5. Prove rollback from an interrupted/failed migration without corrupting the original DB.
6. Independently execute the candidate tests plus relevant V66 regression tests in a checked-out runtime and record commands/results.
7. Keep the rollback anchor at V66 main SHA above until all migration evidence passes.

## Promotion boundary

Only V67 should be considered after these conditions pass. V68+ and media skill branches must remain non-main until V67 is independently eligible or their work is explicitly re-versioned as an independent compatible change.
