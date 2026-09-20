# FAP latest development snapshot

Current additive development release: **V86 — Generic Skill Inventor + Generic Skill Graph**.

Source, tests and integration notes are stored under [`releases/v86/`](releases/v86/).

V86 adds a generic Skill Factory above the current FAP stack:
- V84 AbilityMap can identify a weak capability;
- `SkillInventor` composes verified capability bindings into a declarative DAG;
- `SkillSandbox` executes only verified, deterministic, side-effect-free bindings;
- unit, boundary, deterministic replay and shadow holdouts gate promotion;
- `SkillRegistry` persists only structurally valid evidence-gated state;
- `GenericSkillGraph` executes active skills only;
- `AdaptiveSkillGraphBridge` makes active generic skills available to V82 sparse routing.

Core path:

```text
capability gap
  -> verified binding search
  -> SkillSpec DAG
  -> sandbox
  -> verifier
  -> candidate/testing/shadow/active
  -> Generic Skill Graph
  -> sparse routing
```

V85 remains the production Vision host layer, and V84 remains the autonomous curriculum policy.

**Execution boundary:** invented skills contain binding references and graph structure, not generated source code. V86 cannot grant execution rights to an unverified binding.
