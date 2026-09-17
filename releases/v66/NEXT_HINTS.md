# Next hints after V66 planning

1. **Test event-id collision semantics first.** `QuarantineLedger.failures` currently uses `event_id TEXT PRIMARY KEY`; if upstream event IDs are only unique per capability/request, a same-id event in another capability can be discarded as a duplicate. Decide and document the identity contract, then migrate safely if necessary.
2. **Make restart behavior a release gate.** The staged canary is valuable only if process death cannot reset or accidentally advance rollout evidence. Add kill/reopen/re-evaluate tests around every 5% -> 20% -> 50% -> 100% boundary.
3. **Bound persistent growth.** Canary telemetry and failure evidence are SQLite-backed operational data. Add explicit retention/compaction policy with audit-safe summaries before prolonged Android deployment.
4. **Strengthen Android state writes.** Keep the existing path-sanitization test and add atomic replacement plus corrupted/partial-file recovery.
5. **Tie APK metadata to release evidence.** APK_INFO/build metadata should make the main SHA, release directory, test result, and packaged autonomy sidecar independently checkable. This reduces ambiguity when main advances during a build.
