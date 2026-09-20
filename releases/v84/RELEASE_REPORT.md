# V84 Release Report — Persistent Self-Generated Curriculum

## Implemented

- persistent `AbilityMap` with versioned JSON storage;
- success/frontier/uncertainty/stagnation tracking;
- weakness-aware target selection with anti-starvation exploration;
- slightly-above-frontier task generation;
- explicit solver and independent-verifier interfaces;
- solver/verifier exceptions converted into failed learning observations;
- success-only structural compression;
- replay-resistant evidence digests;
- `ephemeral -> shadow -> consolidated` success-pattern promotion;
- persistent compact pattern store;
- generic `FAPSelfCurriculum` facade;
- concrete `PrimitiveSelfCurriculum` bridge to the V80 Primitive Inventor, Mini-IR Sandbox and Skill Registry;
- compatibility verification configured for V81 local adaptation, V79/V80 creativity/primitive invention and V78 teacher learning.

## Concrete verification path

The V80 bridge self-generates bounded string, number and list transformation tasks. Each uses five training examples including a boundary case and three unseen holdout cases.

A curriculum observation is counted as successful only when the V80 promotion loop reaches `active`.

## Test coverage

The V84 suite covers:
1. success-only compression;
2. rejection of non-independent success;
3. slightly-above-frontier generation;
4. anti-starvation focus selection;
5. ability-map persistence across restart;
6. absence of raw answer text from persisted success patterns;
7. consolidation after three distinct success observations;
8. solver-failure containment;
9. generic facade behavior;
10. real V80 sandbox/promotion bridge behavior.

## Boundary

V84 is a verified learning-policy layer, not fabricated intelligence. The ability frontier advances only after verifier success. The current concrete environment inherits V80's bounded, allow-listed, non-Turing-complete Mini-IR constraints.

## Review fixes carried into V84

- non-independent verifier success cannot advance success count or frontier;
- untrusted verifier reward cannot inflate EMA reward;
- success evidence digests include challenge prompt/difficulty/payload and verifier evidence, preventing restart counter reuse from aliasing distinct challenges.
