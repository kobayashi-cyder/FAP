# FAP latest development snapshot

Current additive development release: **V84 — Persistent Self-Generated Curriculum**.

Source, tests and integration notes are stored under [`releases/v84/`](releases/v84/).

V84 builds on V83 Bidirectional Visual IR Cognition and the V82/V81/V79/V80/V78 learning stack. It adds an upper-level policy for deciding what FAP should practice next and only advancing capability state after independent verification.

V84 adds:
- persistent `AbilityMap` tracking attempts, verified successes, frontier, uncertainty, stagnation and weakness;
- weak/uncertain/underexplored capability selection with anti-starvation coverage;
- slightly-above-frontier self-generated challenges;
- explicit solver and independent-verifier boundaries;
- success-only structural compression rather than persisted raw reasoning traces;
- challenge-bound SHA-256 evidence digests;
- `ephemeral -> shadow -> consolidated` success-pattern promotion;
- concrete bounded Mini-IR curriculum for string, number and list transforms;
- full-stack regression verification through V83, V82, V81, V79/V80 and V78.

V84 also fixes the two blockers found on the earlier Self Curriculum PR:
- `passed=True` without `independent=True` cannot increase verified successes or move the AbilityMap frontier;
- evidence digests bind to the actual generated challenge (prompt, difficulty, payload and related state), so reused task IDs across restarts cannot collapse distinct challenges into one replay identity.

Core loop:

```text
AbilityMap
  -> choose weak / uncertain capability
  -> generate slightly harder task
  -> current FAP solver
  -> independent verifier / holdout
  -> trusted success only
  -> compress reusable structure
  -> update frontier
  -> choose next target
```

**Execution boundary:** V84 is a learning-policy and verification layer. It does not grant arbitrary generated code execution, and capability frontiers do not advance from self-asserted success.
