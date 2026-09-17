# V68 Skill Lane — Evidence Retention + Safe Compaction

Base: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Goal
Bound long-run evidence growth without deleting evidence required for rollback, quarantine, holdout non-reuse, audit, or provenance.

## Prototype
- `evidence_retention.py`
- non-destructive retention planner
- always preserves explicitly protected evidence
- preserves newest N evidence items per capability
- rejects duplicate evidence identities
- deterministic output independent of input order

## Verified locally
- 3/3 unit tests PASS.

## Integration preparation
This branch deliberately plans compaction only; it does not delete files or DB rows. Real deletion must wait for an independently verified reconstructability/audit design.

Required next work:
1. define protected evidence classes from V66 ledgers;
2. produce compacted segment digest + manifest;
3. prove rollback/audit can resolve compacted evidence;
4. simulate disk-pressure and partial-write failures;
5. measure bytes saved vs lookup latency.

Decision gate: KEEP only if storage growth is measurably reduced while protected evidence and rollback proofs remain intact.
