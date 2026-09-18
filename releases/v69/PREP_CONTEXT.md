# FAP v69 Preparation Context

## Inherited main state
- Source branch: `main`
- Source SHA: `929c419b3fcff55720e159b8f7f7f1d602dec305`
- Highest completed release on source main: `v68`
- Rollback anchor: `929c419b3fcff55720e159b8f7f7f1d602dec305`
- Preparation branch: `listener/v69`

## Changed surfaces inherited from v68
V68 adds bounded natural-language TaskPlan parsing, AST patch planning, diagnostic-specific repair, isolated candidate racing, and the V68 code-factory/coordinator path. The relevant implementation surface is concentrated in `fap_autonomy/task_planner.py`, `ast_patch_planner.py`, `diagnostic_repair.py`, `candidate_race.py`, `v68_code_factory.py`, `v68_coordinator.py`, repository-code-factory plumbing, release manifests/demos, and their tests.

## Compatibility constraints
- Preserve V67/V68 safe Code IR and explicit pure-function grammar boundaries; unsupported free-form synthesis must fail closed.
- Keep candidate workspaces isolated and source repositories unchanged until existing verification/promotion gates accept an artifact.
- Preserve V62-V66 static, holdout, resource, lifecycle, canary, rollback, quarantine, trusted-runner and attestation gates.
- Do not mutate Android schema 1/2 writers merely to expose new observability; prefer additive schema evolution.
- Preserve older release/database compatibility and avoid destructive persistence migration.

## Likely implementation targets
1. Android schema-3/provenance observability for generated candidates and packaged artifacts: main SHA, release-manifest digest, verification summary and code-factory lineage.
2. Bounded evidence retention/compaction where needed before adding new provenance records, while pinning evidence referenced by promotion/quarantine/rollback decisions.
3. Extend candidate-race evidence so the canonical winner can be traced without retaining temporary workspace paths or executable payloads.
4. Add restart/persistence tests around any new provenance records and ensure identifiers remain capability/candidate scoped.

## Regression hazards
- Accidental broadening from constrained TaskPlan grammar into arbitrary source generation.
- Candidate race leaking temporary workspace paths, source mutations, or losing deterministic winner selection.
- Provenance keys colliding across capabilities/candidates or becoming stale across restart.
- Retention deleting evidence still referenced by a release, quarantine, canary or rollback decision.
- Android schema changes breaking existing schema 1/2 consumers or increasing payload/storage costs unexpectedly.
- Packaging metadata claiming verification that was not performed for the exact SHA/artifact.

## Android / packaging implications
Prefer an additive schema-3 envelope or optional provenance section. Package diagnostics should identify the exact source main SHA, release manifest digest, candidate lineage and verification/test summary. Existing Android consumers must continue to accept schema 1/2 unchanged. Measure serialized size and avoid embedding bulky raw evidence in APK metadata.

## Required verification
- Re-run V68 delta and V67+V68 cumulative unit suites as baseline.
- `compileall` and warnings-as-errors.
- New provenance serialization/deserialization and backward-compatibility tests for schema 1/2.
- Restart tests for persisted lineage/identity if storage changes.
- Retention tests proving referenced evidence is pinned and unreferenced evidence is bounded.
- Packaging identity test: packaged SHA + manifest digest + verification summary must correspond to the exact prepared artifact.
- Synthetic end-to-end code-factory demo through candidate-ready without source-repository mutation.

## Likely next planned experiment
Build a minimal schema-3 provenance record for one V68 candidate-ready artifact, round-trip it through the Android sync/packaging boundary, restart the persistence layer, and verify exact SHA/manifest/lineage identity while schema-1/2 fixtures remain byte/behavior compatible. If retention growth is material, run bounded compaction with decision-referenced evidence pinned before expanding the schema further.
