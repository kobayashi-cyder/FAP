# FAP V67 Next Hints

Prioritized from the V66 repository state inherited at `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

1. **P0 — Persistence/identity collision tests first.** Exercise identical external event/evidence identifiers under two capability IDs and two candidates. Any uniqueness constraint must match the semantic identity rather than rely on accidental global uniqueness.
2. **P0 — Restart invariants.** Close/reopen SQLite between every canary stage and around quarantine release; prove stale stage observations cannot advance a restarted candidate and released evidence cannot be reused.
3. **P0 — Migration harness before DDL.** Snapshot representative V64/V65/V66 databases and require new code to open them without destructive migration. Add explicit schema-version metadata before changing table keys.
4. **P1 — Evidence retention.** Measure growth of `canary_obs`, authenticated telemetry JSONL, production evidence and quarantine failures. Design retention around audit/rollback requirements; never compact away evidence referenced by a release/quarantine decision.
5. **P1 — Android schema 3 only if needed.** Existing schema 1/2 writers are atomic and should stay stable. Export V66 production/canary confidence data through a new additive schema instead of mutating schema 2.
6. **P1 — Artifact provenance.** Tie APK metadata to main SHA + release manifest digest + verification/test summary so runtime diagnostics can identify exactly what was packaged.
7. **P2 — Statistical calibration experiment.** Simulate healthy, marginal and regressing candidates at the finite N/2N/4N checkpoints; record advance/monitor/rollback rates. Treat the current normal-bound controller as a regression-control heuristic, not formal sequential inference.
8. **P2 — V68/V69 sequence.** If V67 persistence tests pass, use V68 for bounded evidence retention/compaction and V69 for Android schema-3/provenance observability. Re-plan later slots from measured failures rather than filling V70-V1000 speculatively.
