# V68 Skill Lane — Evidence Retention + Safe Compaction

Base: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Goal
Bound long-run evidence growth without deleting evidence required for rollback, quarantine, holdout non-reuse, audit, or provenance.

## Implemented on this non-main branch
- `evidence_retention.py`
  - deterministic non-destructive retention planner
  - preserves explicitly protected evidence
  - preserves newest N evidence items per capability
  - rejects duplicate evidence identities
- `compaction_segment.py`
  - canonical JSONL representation
  - deterministic gzip (`mtime=0`)
  - SHA-256 bound manifest
  - count/raw-size/compressed-size/evidence-ID binding
  - digest/content verification before use
  - atomic temp-write + fsync + replace
- tests for planning, deterministic compaction, tamper rejection, duplicate rejection, round-trip verification, and failed-write preservation.

## Safety boundary
This branch still does **not** delete source files or database rows. A compacted segment is only an additional verified representation. Source deletion must remain disabled until the project proves that all evidence classes needed for rollback, quarantine, holdout non-reuse, audit, and provenance can be resolved from retained source or verified compacted segments.

## Protected evidence classes to bind before deletion
1. active rollback target and its activation/provenance records;
2. quarantine failures still contributing to candidate/family thresholds;
3. every holdout evidence SHA used to release quarantine;
4. attestation/telemetry identities required to prove evidence uniqueness;
5. current canary-stage observations until a stage decision is finalized;
6. audit/provenance records referenced by a promoted capability.

## Next verification
1. generate a manifest from real V66 ledger rows without deleting them;
2. prove lookup by evidence ID resolves exact payload from compacted segment;
3. simulate truncated segment, wrong digest, missing manifest, disk-full/replace failure;
4. measure bytes saved and lookup p50/p95 versus raw JSONL/SQLite export;
5. design a two-phase `compact -> verify -> mark eligible -> later delete` protocol;
6. test that protected-ID calculation survives restart and quarantine release.

Decision gate: KEEP only if storage growth is measurably reduced while protected evidence, anti-reuse constraints, audit lookup, and rollback proofs remain intact.
