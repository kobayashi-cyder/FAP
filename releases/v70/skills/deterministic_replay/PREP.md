# V70 Skill Lane — Deterministic Replay

Base: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Goal
Capture normalized observation/decision/action/seed sequences so regressions can be reproduced exactly or detected as divergence.

## Prototype
- `deterministic_replay.py`
- canonical JSON hashing
- per-step digest
- whole-trace digest
- explicit random seed
- replay verification by expected digest

## Verified locally
- 2/2 unit tests PASS.

## Integration preparation
The prototype is intentionally transport-agnostic. Integration should normalize unstable fields (timestamps, transient window IDs) before hashing rather than masking mismatches after the fact.

Required next work:
1. define Android observation normalization;
2. record action outcome/postcondition;
3. version the trace schema;
4. replay V66 healthy rollout and rollback/quarantine cycle;
5. measure nondeterminism rate and trace size.

Decision gate: KEEP only if the same captured task reproduces deterministically enough to improve regression debugging without excessive storage.
