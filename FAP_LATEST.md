# FAP latest development snapshot

Current additive development release: **V82 — Sparse Adaptive Circuit Orchestrator**.

Source, tests and integration notes are stored under [`releases/v82/`](releases/v82/).

V82 builds on the current stack:
- V80 Primitive Inventor / Mini-IR Sandbox / Skill Registry promotion loop;
- V81 Local Adaptive Predictive Core;
- V79 Creativity Success Learning;
- V78 teacher-learning guidance.

V82 adds:
- verifier-first execution rights for specialist circuits;
- sparse top-k routing with a relevance activation threshold, so unrelated inputs may activate zero optional circuits;
- success-only bounded Active Memory that biases future routing;
- bounded deterministic circuit mutation with unroutable candidate children;
- automatic failure quarantine and execution-right revocation;
- V79 creative operators as sparse specialists instead of an always-on five-operator pass;
- V81 local adaptation as a sparse specialist instead of an always-on adaptive pass;
- V80 `active` Mini-IR primitives as verifier-rechecked executable specialists;
- shared routing competition across specialist families so only a few small circuits run per task.

Combined direction:

```text
invent / local-learn / existing specialist
        ↓
independent verification evidence
        ↓
eligible circuit pool
        ↓
relevance threshold
        ↓
top-k sparse route
        ↓
execute selected small circuits only
        ↓
verify outcome
        ↓
success-only Active Memory
        ↓
promote / quarantine / bounded evolution
```

**Execution boundary:** arbitrary generated Python/native code is still not granted execution rights. Self-invented executable skills remain constrained by the V80 allow-listed Mini-IR sandbox.
