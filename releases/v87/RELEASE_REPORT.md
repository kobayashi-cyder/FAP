# V87 Release Report — Autonomous Improvement Core

## Source audit

Library artifact: `FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip`

SHA-256: `660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7`

Independent local rerun:
- source V82 tests: 10/10 PASS;
- source V90 tests: 6/6 PASS;
- source TEST_REPORT.json says V90 7/7, but the archive contains six V90 test methods.

## Implemented on current main

- `FAPEval` and failure clustering;
- V86 declarative `SkillEvolution` by eligible binding substitution only;
- benchmark-before / trial / settled benchmark-after;
- largest failure-cluster targeting with V84 weakness tie-break;
- V86 Inventor + verifier/shadow promotion for repairs;
- strict target-improvement + non-regression acceptance gate;
- quarantine of promoted but non-improving trials from V87 adoption;
- optional accepted-skill synchronization into the V82 sparse-routing bridge;
- independent benchmark evidence fed back to V84 AbilityMap.

## Not copied

The source artifact's duplicate Capability Map, Self Curriculum, Sparse Router, Verifier First, Active Memory and Skill Inventor implementations are superseded by current V84/V82/V86 mainline systems.
