# V70 decision — Deterministic replay

Decision: MODIFY pending independent CI.

Rollback anchor: main `e338d9bb70afd7d46fd2465feaedc3d133630e6a` (V69).

This branch selectively reimplements the stale V70 replay idea against current V69 main. It adds canonical JSON replay envelopes, SHA-256 binding of ordered events plus explicit config, duplicate/missing identity rejection, schema rejection, privacy/nondeterminism field rejection, injected reducer execution, explicit failure results, fresh-process repeatability tests, and a 10,000-event resource probe.

Promotion requires the dedicated GitHub Actions matrix to complete successfully on Python 3.11 and 3.12, including focused V70 tests and V69 interaction regression. Until that external run is observed, no PASS/KEEP claim is made.

Limitations: synthetic events only; no production/Android event adapter claim, no arbitrary code/network/provider replay, no timing-sensitive concurrency replay. Timeout enforcement is intentionally outside this pure reducer slice; reducer exceptions fail closed. Rollback is removal of `releases/v70/` and the V70 workflow; no state migration is introduced.
