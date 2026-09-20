# FAP latest development snapshot

Current additive development release: **V81 — Sparse Adaptive Circuits**.

Source, tests and integration notes are stored under [`releases/v81/`](releases/v81/).

V81 is additive on top of:
- V80 Primitive Inventor -> Mini-IR Sandbox -> SkillRegistry promotion loop;
- V79 Creativity Success Learning;
- V78 Gemma 4 Direct-Learning Integration.

V81 adds:
- verifier-first execution rights for every adaptive circuit;
- sparse top-k specialist routing, defaulting to two circuits per task;
- success-only bounded Active Memory;
- deterministic bounded circuit mutation with unroutable candidate children;
- verified promotion and automatic failure quarantine/revocation;
- sparse V79 creativity execution so only routed operators run;
- V80 PrimitiveCircuitBridge: only evidence-promoted `active` Mini-IR primitives are adopted into the runtime circuit pool;
- runtime outcomes feed back into Active Memory and future routing;
- V78 teacher-learning composition through `build_v81_responder()`.

The combined direction is now:

```text
invent / mutate
→ sandbox + verifier
→ shadow evidence
→ active/consolidated
→ sparse route
→ execute only needed circuits
→ verify outcome
→ retain successful routing memory
→ evolve again
```

**Important boundary:** executable self-invention remains constrained to the V80 allow-listed, non-Turing-complete Mini-IR. V81 does not grant arbitrary generated code execution rights.
