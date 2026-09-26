# FAP V86 — Generic Skill Inventor + Generic Skill Graph

V86 closes the gap between primitive invention and domain-specific visual skill graphs by adding a generic verifier-gated Skill Factory.

The system does **not** invent arbitrary Python. It invents declarative DAGs whose nodes may reference only pre-registered bindings that the host has already marked:

- verified;
- deterministic;
- side-effect-free.

## Closed loop

```text
V84 AbilityMap weakness
  -> required capability tags
  -> SkillInventor
  -> declarative SkillSpec DAG
  -> bounded SkillSandbox
  -> unit + boundary verification
  -> deterministic replay
  -> shadow holdouts
  -> SkillRegistry
  -> active GenericSkillGraph
  -> V82 sparse routing
  -> verified runtime result
```

## Generic Skill IR

A skill contains only:
- skill id;
- name / ability / tags;
- nodes referencing existing `binding_id` values;
- DAG edges;
- one output node.

No source/code/import/eval field exists. Skill identity is SHA-256-derived from its declarative structure and is recomputed when persisted state is loaded.

## Sandbox

`SkillSandbox` enforces:
- maximum 12 nodes;
- acyclic graph;
- no dead nodes outside the output dependency chain;
- only eligible bindings;
- simple-data inputs/outputs only;
- payload-size bounds;
- execution time budget evidence.

The sandbox does not claim to preempt a malicious host callback. Bindings are host-trusted primitives/capabilities; invented skills can only compose them.

## Promotion

A generic skill must pass:
- at least three unit cases;
- at least one boundary case;
- deterministic double execution;
- no timeout-budget breach;
- at least three successful shadow/holdout cases.

Lifecycle:

`candidate -> testing -> shadow -> active/rejected`

Persisted active skills fail closed if promotion evidence, graph identity, or required binding eligibility is missing.

## V84 bridge

`CapabilitySkillFactoryBridge` allows a weak V84 ability to request a V86 build. The AbilityMap advances only after the new skill reaches `active` through independent Skill Factory verification.

## V82 bridge

`AdaptiveSkillGraphBridge` registers only active V86 skills into the V82 sparse router. The generic skill remains a bounded binding DAG; sparse routing does not create execution rights for unverified candidates.
