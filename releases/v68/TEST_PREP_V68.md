# TEST PREP V68 — Evidence Retention + Safe Compaction

Verification baseline: current `main` = `162202f0d955f2ac15ee8c4b6bf0faf83b586ea6` (V67 native repository code factory stage 1). V68 remains non-destructive and independently testable; no source evidence deletion is eligible in this cycle.

## Gate 0 — classify the existing red regression first

The prior V68 branch reported focused tests/compile green while broad `releases/v66/tests` discovery was red on Python 3.11 and 3.12. Re-run the exact failing discovery command on both current main and the V68 head in clean environments. Record command, interpreter, exit code, first failing test/trace, and whether failure reproduces on main. Do not label V68 regression unless the failure is branch-specific. Do not waive a main-baseline failure; record it separately and keep promotion blocked until the relevant cumulative gate is green or the test is demonstrably obsolete and replaced by an equivalent/harder check.

## Deterministic functional tests

1. Retention planning over identical records in shuffled order must yield byte-identical plan/manifest/segment output.
2. Reject blank IDs/capabilities, duplicate stable identities, malformed/non-finite timestamps, invalid retention counts, malformed manifests, unknown schema versions, and non-canonical payloads.
3. Use a V66/V67-shaped fixture containing rollback/provenance anchors, quarantine failures and release cutoffs, globally single-use holdout hashes, attestation/telemetry identities, active canary evidence, and V67 repository-code-factory evidence/state where applicable.
4. Every protected record must remain directly resolvable after compaction. Resolve by stable identity, verify segment+manifest before returning data, and compare canonical payload SHA-256 with untouched source evidence.
5. Corrupt one byte, truncate gzip/JSONL, reorder or duplicate records, alter count/digest/capability/timestamp bounds, swap manifests, remove a protected record, and inject an unsupported schema. Every case must fail closed; no partially verified record may be returned.
6. Simulate partial write, destination ENOSPC, readonly destination, interrupted temp-file/rename sequence, process restart, duplicate retry, and stale temp files. Untouched source remains authoritative until atomic verification completes.
7. Restart/reindex must preserve lookup equivalence and must not convert a corrupt segment into usable evidence.

## Cross-version regression

Run V67's independently accepted persistence-identity tests plus the current main V67 native repository code factory tests before promotion. Specifically preserve globally single-use attestation/holdout semantics, capability-scoped event identities, migration/rollback behavior, and repository-factory safety gates. Run compileall and warnings-as-errors on the changed Python surface.

## Resource evidence

For fixed small/medium/large fixtures record: source bytes, compressed bytes, compression ratio, peak temporary disk bytes, peak RSS if measurable, compaction wall time, resolver lookup p50/p95, restart/reindex wall time, and failed-write residue. KEEP requires measurable storage reduction and no unexplained pathological lookup/RAM regression; raw numbers must be retained rather than only a pass/fail label.

## Security / privacy / retention assertions

Compaction must not broaden retention, expose secrets in manifests/logs, weaken attestation or holdout anti-reuse, or discard audit/rollback provenance. Manifest metadata must be the minimum required for verification/indexing. Source deletion, lifecycle pruning, remote upload, encryption-at-rest claims, and retention-policy changes remain outside this gate unless separately implemented and independently tested.

## Acceptance and rollback

KEEP only if focused tests, corruption/failure injection, current-main cumulative regression, exact reconstruction, protected-class lookup equivalence, and resource evidence are independently green on the same candidate SHA. MODIFY if resolver/protected mapping/resource evidence is incomplete. DEFER destructive deletion even if non-destructive compaction passes. REPLACE/KILL if exact audit/rollback/anti-reuse semantics cannot survive compaction.

Rollback/disable anchor: disable compacted-segment creation and resolution, ignore untrusted/new segment artifacts, and continue reading untouched source evidence. No database migration or source deletion may be required for rollback.

## Highest-risk untested assumptions

- Existing V68 branch was prepared against V66 and has not yet demonstrated compatibility with current V67 native repository code factory state.
- The prior broad regression failure has not yet been classified against current main.
- Exact lookup equivalence for all protected V66/V67 evidence classes is not yet independently demonstrated.
- Resource benefit and restart/reindex cost are not yet measured on representative fixtures.
