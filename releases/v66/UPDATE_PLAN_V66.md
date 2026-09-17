# FAP V66 update plan

Source main SHA: `ee72c1068c643172118f6afdf7bd90e7efe29d16`

## Assessment

V65 adds the operational staged-canary/quarantine loop and substantially expands the cumulative release tree. The core design is coherent: verified telemetry feeds isolated canary stages, regressions trigger rollback/demotion, repeated regressions quarantine candidates/families, and Android receives a sanitized state export.

No speculative runtime change is being made in this listener iteration because the new V65 delta already records 18/18 passing delta tests and the next safe step is to harden persistence/recovery semantics rather than alter rollout behavior without a focused regression suite.

## V66 target

Harden the operational loop for restart, persistence, and long-running-device use.

1. Quarantine ledger integrity
   - verify event identity is safely namespaced across capabilities/candidates rather than relying on a globally unique external event id;
   - add schema/version handling before changing the SQLite key shape;
   - test duplicate replay, cross-capability same-id events, and restart persistence.
2. Canary restart recovery
   - reconstruct stage/ratio/evidence boundaries after process death;
   - prove evidence from an earlier stage cannot satisfy a later gate after restart.
3. Atomic Android state publication
   - write temporary file + fsync/replace where supported;
   - retain the no-slot-path invariant;
   - add malformed/partial-state recovery tests.
4. Operational retention
   - define bounded telemetry/failure-ledger retention so Android storage cannot grow without limit;
   - preserve enough evidence for rollback/quarantine auditability.
5. Packaging validation
   - confirm the Android packaging workflow selects V65/V66 autonomy sidecars deterministically;
   - run compileall, unit tests, and an APK build before promotion.

## Acceptance gate

V66 should not be promoted until restart/replay tests pass, SQLite migration is backward-compatible with an existing V65 database, Android export remains sanitized, and the APK workflow completes from the same source SHA used by the release manifest.
