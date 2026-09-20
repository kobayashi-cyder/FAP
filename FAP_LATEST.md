# FAP latest development snapshot

Current additive development release: **V84 — Persistent Self-Generated Curriculum**.

Source, tests and integration notes are stored under [`releases/v84/`](releases/v84/).

V84 builds on V83 Bidirectional Visual IR Cognition and the existing V82/V81/V80/V79/V78 learning stack. It adds a verifier-gated learning policy that decides what FAP should practice next rather than only accumulating whatever experience arrives.

V84 adds:
- persistent `AbilityMap` state for attempts, independently verified successes, frontier, uncertainty and stagnation;
- weak/uncertain/underexplored capability selection with anti-starvation exploration;
- frontier-stretching challenge generation;
- independent solver/verifier separation;
- success-only structural compression with no persisted raw reasoning trace;
- replay-resistant evidence bound to the full generated challenge, attempt evidence and verifier evidence;
- `ephemeral -> shadow -> consolidated` reusable success-pattern promotion;
- concrete self-generated string/number/list tasks through the bounded Primitive Inventor / Mini-IR Sandbox / Skill Registry loop;
- fail-closed behavior where non-independent verifier success cannot advance the ability success count or frontier;
- regression verification across V83, V82, V81, V79/V80 and V78 on Python 3.11 and 3.12.

Core loop:

```text
AbilityMap
  -> choose weak / uncertain capability
  -> generate a slightly harder challenge
  -> solve with current FAP mechanisms
  -> independent verification
  -> success only: compress reusable structure
  -> update verified frontier
  -> choose next learning target
```

**Execution boundary:** V84 does not fabricate competence. Capability growth is recorded only from independent verifier success. The concrete primitive curriculum remains inside the bounded, allow-listed, non-Turing-complete Mini-IR environment.
