# FAP v69 Next Hints

Prepared from main `929c419b3fcff55720e159b8f7f7f1d602dec305` after completion of v68.

1. **P0 — Provenance identity first.** Define an additive, exact identity tuple for source main SHA, release-manifest digest, candidate/capability lineage and verification summary. Never infer verification from version labels alone.
2. **P0 — Backward compatibility.** Keep Android schema 1/2 readers/writers behavior stable. Introduce schema 3 only as additive observability with explicit downgrade/absence behavior.
3. **P0 — Restart invariants.** Persist and reload provenance/identity without allowing stale candidate or canary evidence to advance a different candidate after restart.
4. **P0 — Evidence pinning before compaction.** Any retention mechanism must preserve evidence referenced by release, quarantine, promotion, canary and rollback decisions.
5. **P1 — Candidate-race lineage.** Record winning strategy and canonical patch identity without persisting temporary workspace paths or executable payloads.
6. **P1 — Packaging attestation.** Bind packaged diagnostics to the exact main SHA + release-manifest digest + tests/verification actually performed for that artifact.
7. **P1 — Size budget.** Measure schema-3 serialized payload and persisted evidence growth; keep raw benchmark/test evidence outside APK metadata where a digest/reference is sufficient.
8. **P2 — Experiment.** Produce one v68-derived candidate-ready artifact, round-trip provenance through Android sync/packaging, restart storage, then verify identity and schema-1/2 compatibility. Use measured failures to decide whether v69 should prioritize retention or broader observability.

Rollback anchor: `929c419b3fcff55720e159b8f7f7f1d602dec305`.
