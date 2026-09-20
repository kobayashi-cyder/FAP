# FAP latest development snapshot

Current additive development release: **V82 — Persistent Self-Generated Curriculum**.

Source, tests and integration notes are stored under [`releases/v82/`](releases/v82/).

V82 is additive on top of V81 Local Adaptive Predictive Core, the V80 Primitive Inventor / Mini-IR Sandbox / Skill Registry promotion loop, V79 Creativity Success Learning and V78 Gemma 4 Direct-Learning Integration.

V82 adds a new upper-level function: FAP can maintain a persistent map of its own verified capabilities, identify weak or uncertain areas, generate a task slightly above the current frontier, test itself in an independent environment, retain only compressed successful structure, and then choose what to learn next.

V82 adds:
- persistent `AbilityMap` storage for attempts, verified successes, success rate, EMA reward, frontier, uncertainty and stagnation;
- weakness-aware target selection with exploration bonuses and repetition penalties;
- automatic challenge generation just beyond the current verified frontier;
- solver/verifier failure containment;
- success-only structural compression without persisted raw reasoning traces;
- replay-resistant evidence digests;
- `ephemeral -> shadow -> consolidated` pattern promotion after 1/2/3 distinct verified observations;
- persistent compact success-pattern storage;
- generic curriculum integration for decomposition, composition, generalization, verification, repair and creative transfer;
- a concrete V80 bridge that self-generates bounded string, number and list exercises;
- concrete verification through five training cases including a boundary case plus three unseen holdout cases before the V80 promotion loop may count the result as `active`.

V81 remains the cheap local predictive-adaptation substrate. V82 sits above it as a curriculum policy: it decides **which capability should receive learning effort next**.

The V82 workflow is configured to run its own tests plus V81 local-adaptation, V79/V80 creativity/primitive-invention and V78 teacher-learning regressions on Python 3.11 and 3.12.

**Important limitation:** V82 implements autonomous curriculum selection and verified capability updating; it does not fabricate competence. The ability frontier advances only after independent verification succeeds.
