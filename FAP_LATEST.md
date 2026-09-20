# FAP latest development snapshot

Current additive development release: **V81 — Self-Generated Curriculum**.

Source, tests and integration notes are stored under [`releases/v81/`](releases/v81/).

V81 is additive on top of the V80 Primitive Inventor -> Mini-IR Sandbox -> Skill Registry promotion loop, V79 Creativity Success Learning and V78 Gemma 4 Direct-Learning Integration.

The change is architectural: FAP no longer has to improve only by accumulating more Primitives. V81 gives it a learning controller that can decide **what capability to practice next**.

V81 adds:
- an `AbilityMap` with attempts, verified successes, success rate, EMA reward, verified frontier, uncertainty and stagnation;
- weakness-aware target selection with exploration bonuses and repetition penalties;
- generation of challenges slightly above the current verified frontier;
- generic current-FAP solver and independent-verifier interfaces;
- solver/verifier failures converted into learning observations instead of crashing the loop;
- success-only irreversible compression that does not persist raw reasoning traces;
- replay-resistant evidence digests;
- `ephemeral -> shadow -> consolidated` reusable-pattern promotion after 1/2/3 distinct verified observations;
- a generic `FAPSelfCurriculum` facade for abstract abilities such as decomposition, composition, generalization, verification, repair and creative transfer;
- a concrete `PrimitiveSelfCurriculum` bridge that generates bounded practice tasks and runs them through the existing V80 Primitive Inventor, Mini-IR Sandbox and Skill Registry;
- real holdout verification: five training tests including a boundary case plus three unseen shadow cases before a primitive counts as a V81 learning success.

The concrete V80 bridge currently trains bounded string normalization, numeric transforms and list transforms. Broader reasoning domains can be added by supplying additional task generators and independent verifiers without changing the core curriculum loop.

CI verifies V81 plus the V79 creativity/V80 primitive-invention regressions and V78 teacher-learning regressions on Python 3.11 and 3.12.

**Important limitation:** V81 implements autonomous curriculum selection and verified capability updating; it does not fabricate competence. The ability map advances only after independent verification succeeds.
