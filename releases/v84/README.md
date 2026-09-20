# FAP V84 — Self-Generated Curriculum

V84 adds a persistent self-generated curriculum controller above V83 Bidirectional Visual IR Cognition and the current FAP learning stack.

The key change is that FAP no longer has to improve only by accumulating primitives or passively adapting from whatever experience happens to arrive. It now has a mechanism for deciding **what it should practice next**.

## Closed loop

```text
persistent AbilityMap
  -> select weak / uncertain / underexplored capability
  -> create a task slightly above the verified frontier
  -> solve with the current FAP stack
  -> independent sandbox / holdout verification
  -> success: compress reusable structure only
  -> 1/2/3 evidence: ephemeral -> shadow -> consolidated
  -> failure: update capability statistics only
  -> persist frontier / uncertainty / stagnation
  -> choose the next learning target
```

## Ability map

The generic controller supports abstract capabilities such as:
- decomposition
- composition
- generalization
- verification
- repair
- creative_transfer

Each capability tracks:
- attempts;
- verified successes;
- success rate;
- EMA reward;
- highest verified frontier;
- uncertainty;
- stagnation;
- derived weakness.

The map is persisted as `fap.ability-map.v1`, so restarts do not erase what FAP has learned about its own strengths and weaknesses.

Focus selection includes:
- weakness priority;
- uncertainty priority;
- an exploration bonus for untried capabilities;
- a repetition penalty.

That prevents a single stubborn weakness from consuming the entire curriculum.

## Slightly harder task generation

The default target is:

`next = frontier + stretch * (0.75 + uncertainty)`

Early exploration is broader. As evidence accumulates and uncertainty falls, the step size tightens.

## Success-only compression

V84 does not persist a raw reasoning trace.

`SuccessCompressor` keeps only:
- capability name;
- a compact structural signature;
- short summary;
- verified difficulty;
- reward;
- evidence digest.

Promotion requires distinct verified observations:

`ephemeral -> shadow -> consolidated`

Failed attempts update the capability map but are not added to reusable success memory.

## Concrete bridge to V80

`PrimitiveSelfCurriculum` directly connects V84 to the existing V80:

`Primitive Inventor -> Mini-IR Sandbox -> Skill Registry -> Promotion Loop`

The current bounded curriculum can self-generate exercises in:
- string normalization;
- numeric transforms;
- list transforms.

Every concrete exercise has:
- five training examples;
- at least one boundary case;
- three unseen holdout/shadow cases.

Only a candidate that V80 promotes to `active` counts as a V84 success.

This means the first concrete V84 curriculum does not merely mark its own answer correct. It delegates the judgment to the existing bounded sandbox and promotion system.

## Relationship to V81

V81 provides cheap verifier-gated local predictive adaptation. V84 is an upper-level learning-policy layer: it decides which capability to exercise and when to increase difficulty. V81 can remain a local adaptation substrate while V84 controls curriculum selection.

## Scope

V84 implements the autonomous curriculum mechanism and one real verified practice environment. It does not claim arbitrary competence. Expanding beyond Mini-IR requires additional safe task generators and independent verifiers for new reasoning domains.


## V84 review hardening

V84 additionally requires independent verifier evidence before AbilityMap success/frontier advancement and binds replay digests to the full generated challenge, attempt evidence, and verifier evidence so restarts cannot alias a different harder challenge onto an old digest.
