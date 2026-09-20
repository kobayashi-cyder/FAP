# V84 Release Report — Persistent Self-Generated Curriculum

## Implemented

- persistent versioned `AbilityMap`;
- weakness/uncertainty/coverage-aware target selection;
- slightly-above-frontier challenge generation;
- explicit solver and independent-verifier interfaces;
- fail-closed solver/verifier exception handling;
- independent-verifier gate for AbilityMap success/frontier advancement;
- success-only compressed structural memory;
- challenge-bound SHA-256 evidence digests;
- replay-resistant `ephemeral -> shadow -> consolidated` promotion;
- persistent compact pattern store;
- generic `FAPSelfCurriculum` facade;
- concrete bounded Mini-IR primitive curriculum;
- current-main V78 provenance, V79 experience, and V80 primitive-registry persistence hardening as prerequisites.

## Fixed from the older PR #37 proposal

1. Non-independent `passed=True` verifier results no longer increase successes or frontier.
2. Evidence digests now include the generated challenge content rather than relying primarily on a restart-reusable task id.

## V84 tests

The V84 suite includes the original curriculum coverage plus regressions proving:
- non-independent success cannot advance the frontier;
- two different challenges sharing one task id produce distinct evidence digests and can accumulate distinct promotion evidence.

The dedicated workflow also runs V83, V82, V81, V79/V80 and V78 regression suites on Python 3.11 and 3.12.

## Promotion rule

V84 must not be marked MAIN until the dedicated workflow and review complete successfully.
