# V90 Source Artifact Audit

Source Library artifact: `FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip`

SHA-256: `660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7`

## Independent standalone reproduction

The artifact contains:
- `fap_v90/core.py`;
- `tests_v90/test_v90.py`;
- a bundled historical `fap_v82/` implementation and `tests/test_v82.py`.

Independent discovery reproduced:
- V90 suite: **6/6 PASS**;
- bundled legacy V82 suite: **10/10 PASS**.

The older shared-state handoff said `v90_suite: 7/7 PASS`, but the supplied ZIP contains six discoverable test methods in `tests_v90/test_v90.py`. The rebased mainline therefore records 6/6 as the independently reproduced source-artifact count and keeps 7/7 only as historical reported metadata.

## What was not merged

The following artifact components duplicate or predate current verified mainline code and were deliberately not copied into V90:
- historical `CapabilityMap` -> superseded by V84 AbilityMap;
- historical `SelfCurriculum` -> superseded by V84;
- historical `SparseRouter` -> superseded by V82;
- historical primitive-sequence `SkillInventor` / `SkillPromotionLoop` -> superseded by hardened V80 and generic V86;
- bundled `fap_v82/` snapshot -> not imported.

## What was rebased

- `FAPEval` -> current independent benchmark harness;
- `AutonomousImprovementCore` -> V84/V86/V82-aware improvement loop;
- `SkillEvolution` -> declarative V86 graph mutation only;
- benchmark-before/after discipline -> strengthened into staged global deployment gate;
- boundedness -> preserved; no generated Python execution.

## Promotion requirement

V90 is MAIN only after its own Python 3.11/3.12 workflow and the V86/V85/V84/V83/V82/V81/V79-V80/V78 regression suites pass on the rebased source.
