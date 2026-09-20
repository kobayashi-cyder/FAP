# V90 Release Report — Rebased Autonomous Improvement Core

## Implemented

- independent `FAPEval` with per-ability scorecards and failure clusters;
- replay-protected persistent `CycleLedger`;
- V86 local Skill promotion integration;
- staged V90 deployment gate;
- whole-suite no-regression check;
- target-ability improvement requirement;
- accepted Skill adoption into the V82 sparse router;
- failed global trial revoke/quarantine;
- post-deployment regression rollback;
- final-state-only V84 AbilityMap update;
- bounded declarative V86 Skill Evolution.

## Source artifact reproduction

Before rebase:
- artifact V90 tests: 6/6 PASS;
- bundled historical V82 tests: 10/10 PASS.

## Rebased V90 tests

1. FAP-Eval clusters failures and contains solver exceptions;
2. failure cluster can generate, verify and globally deploy a repair;
3. local Skill promotion is rolled back when another ability regresses;
4. no-failure baseline performs no invention;
5. improvement cycle IDs are replay-protected across restart;
6. Skill Evolution uses verified binding references only;
7. pre-promotion Skill cannot enter deployment;
8. wrong-ability proposal cannot deploy;
9. failed repair updates AbilityMap from final state only.

The dedicated workflow also runs all current V86, V85, V84, V83, V82, V81, V79/V80 and V78 regressions on Python 3.11 and 3.12.
