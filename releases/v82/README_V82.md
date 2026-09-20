# FAP V82 — Sparse Adaptive Circuits

V82 is additive on top of the V80 Primitive Inventor loop and the V79/V78 creativity + teacher-learning stack.

## Added

- **Verifier First execution rights**: uncertified or quarantined circuits cannot enter runtime routing.
- **Sparse routing**: default top-2 specialist activation per task.
- **Active success memory**: only verified successful traces become short-lived routing priors.
- **Bounded circuit evolution**: consolidated circuits emit deterministic parameter mutations; children remain unroutable candidates until separately certified.
- **Promotion / quarantine**: verified success promotes `candidate -> ephemeral -> shadow -> consolidated`; repeated failure revokes execution rights.
- **V79 creativity binding**: only routed creativity operators are rendered instead of running all five operators every turn.
- **V80 Primitive bridge**: only SkillRegistry entries already promoted to `active` after Sandbox, automatic tests, boundary checks, determinism checks and Shadow successes are adopted as executable specialist circuits.
- **V78 composition**: `build_v82_responder()` preserves teacher-learning guidance.

## Combined loop

```text
Self-generated task / external task
    ↓
Primitive Inventor (V80)
    ↓
Mini-IR Sandbox
    ↓
candidate → testing → shadow → active
    ↓
PrimitiveCircuitBridge (V82)
    ↓
Verifier First eligibility
    ↓
Sparse Router (top-k only)
    ↓
selected small circuits execute
    ↓
outcome verification
    ↓
success-only Active Memory
    ↓
promotion / quarantine / bounded evolution
    └──────────────→ next candidate circuit
```

Evolution never grants itself execution rights. Mutation/invention proposes; independent evidence gates execution.
