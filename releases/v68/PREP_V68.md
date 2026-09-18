# PREP V68 — Evidence Retention + Safe Compaction

Baseline: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e` (V66). V68 remains independent of V67 schema promotion.

## Current status
The V68 retention planner and deterministic compacted-segment implementation exist on `skill/v68-evidence-retention`. Their focused tests and compile step pass in GitHub Actions, but the branch CI is currently red because the broad `releases/v66/tests` discovery regression step fails on both Python 3.11 and 3.12. Therefore V68 is **not** promotion-ready and no KEEP decision should be inferred from the focused tests alone.

## Smallest next implementation step
1. Reproduce/classify the V66 regression failure before changing V68 implementation. Distinguish a branch regression from a baseline/environment test-discovery failure.
2. Keep source deletion disabled. Treat compacted segments as additional representations only.
3. Add a resolver that retrieves an evidence record by stable identity from a verified segment and compares its canonical payload hash to source evidence.
4. Build a real V66-shaped fixture covering rollback/provenance, quarantine failures, holdout non-reuse identities, attestation/telemetry identities, and active canary evidence.
5. Exercise corrupt/truncated/wrong-manifest and interrupted-write paths fail-closed.
6. Record source bytes, compressed bytes, temporary peak bytes, compaction time, lookup p50/p95, and restart/reindex cost.

## Promotion evidence
Promotion requires: focused V68 tests green; independently classified/green baseline regression; exact reconstruction of protected evidence; tamper/failure injection; measurable storage reduction; rollback/audit/quarantine/holdout lookup equivalence; explicit rollback anchor. Destructive deletion remains DEFER even if non-destructive compaction is KEEP.

## Rollback
Disable creation/use of new compacted segments and continue resolving untouched source evidence. V68 must not require a database migration or delete source rows/files.

## Decision conditions
- KEEP: non-destructive compaction + resolver meet all evidence gates and regression is green/classified.
- MODIFY: protected-class mapping, resolver semantics, resource evidence, or CI classification is incomplete.
- DEFER: deletion, lifecycle pruning, or V67-dependent schema integration.
- REPLACE/KILL: compacted representation cannot preserve exact audit/rollback/anti-reuse semantics.
