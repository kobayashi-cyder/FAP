# V81 Release Report — Self-Generated Curriculum

## Implemented

V81 adds the next layer above the Primitive Inventor loop:

- persistent-capable `AbilityMap` state model;
- weakness, uncertainty, frontier and stagnation tracking;
- anti-starvation target selection;
- self-generated challenges slightly above the current frontier;
- explicit current-FAP solver and independent-verifier interfaces;
- failure-to-statistics handling without failed-trace memorization;
- irreversible success-pattern compression;
- replay-resistant evidence digests;
- `ephemeral -> shadow -> consolidated` pattern promotion;
- generic `FAPSelfCurriculum` integration;
- concrete `PrimitiveSelfCurriculum` bridge to V80 Primitive Inventor, Mini-IR Sandbox and Skill Registry.

## V80 bridge verification target

The concrete bridge generates bounded tasks for string normalization, numeric transforms and list transforms. Each task contains five training tests including a boundary case and three unseen shadow/holdout tests. A curriculum success requires V80 to promote the invented primitive to `active`.

## Test coverage

The V81 suite checks:
1. verified success is compressed while failure is not;
2. non-independent success cannot enter memory;
3. generated difficulty stays just above the current frontier;
4. exploration prevents starvation of untried abilities;
5. persisted memory does not contain the raw answer;
6. three independent observations consolidate a reusable pattern;
7. solver exceptions become learning failures rather than crashing the loop;
8. the generic facade updates and exposes the capability map;
9. the concrete bridge runs through the real V80 primitive sandbox/promotion path.

CI also runs the V79 creativity/Primitive-Inventor tests and V78 teacher-learning regressions on Python 3.11 and 3.12.

## Boundary

This is a learning-policy mechanism, not fabricated competence. A task advances the ability map only when the configured independent verifier accepts it. The concrete bridge therefore inherits V80's allow-listed, non-Turing-complete sandbox constraints.
