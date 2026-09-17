# V68 Evidence Retention Test Preparation

Baseline: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`. V68 must remain independently testable and must not depend on V67 schema promotion.

## Deterministic verification
1. Run retention planner tests under shuffled input order; identical records must produce byte-identical keep/compact plans.
2. Reject duplicate IDs, blank IDs/capabilities, invalid keep counts, malformed timestamps, and non-finite timestamps.
3. Protect every class needed by V66 rollback/quarantine/holdout/provenance: active rollback anchors, quarantine failures inside release cutoffs, globally single-use holdout evidence hashes, attestation/provenance references, and current canary evidence.
4. Segment/manifest tests must prove canonical serialization, stable SHA-256, record count, capability coverage, min/max timestamps, and source digest linkage.
5. Corrupt one byte, truncate a segment, reorder records, duplicate a record, mismatch manifest count/digest, and remove a referenced protected item; resolver must fail closed.
6. Simulate partial write, ENOSPC, readonly destination, interrupted rename, and restart. Original evidence remains authoritative until a fully verified compacted segment is atomically committed.
7. Reconstruct every compacted record from segment+manifest and compare canonical payload hashes with the source fixture before any deletion experiment.
8. Verify rollback/audit/quarantine/holdout lookup paths can resolve both live and compacted evidence without semantic differences.

## Resource evidence
Use reproducible small/medium/large fixtures. Record source bytes, compacted bytes, peak temporary bytes, compaction wall time, lookup p50/p95, and restart/reindex time. KEEP requires meaningful storage reduction without unacceptable lookup regression.

## Safety boundary
No destructive deletion is eligible in V68 until reconstructability and lookup integration are independently exercised. Compaction planning/segment creation may be KEEP while deletion remains DEFER.

## Acceptance
KEEP only with clean-runtime tests, corruption/failure injection, canonical digest evidence, complete protected-class mapping, and measured storage benefit. MODIFY if any protected class or resolver path is missing. KILL/REPLACE if compacted evidence cannot preserve audit/rollback semantics.

Rollback/disable: stop producing new segments and continue using untouched source evidence; no source deletion is permitted by this test plan.