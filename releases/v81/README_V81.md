# FAP V81 — Self-Generated Curriculum

V81 turns the existing FAP learning stack into a closed curriculum loop.

It sits above V80's Primitive Inventor -> Mini-IR Sandbox -> Skill Registry promotion loop and above V79/V78. Instead of only adding more Primitives, V81 tracks **what kinds of thinking are weak**, selects the next learning target, creates a slightly harder task, verifies it in a bounded environment, compresses only successful structure, and updates the ability frontier.

## Closed loop

```text
AbilityMap
  -> select weak / uncertain / underexplored ability
  -> generate task slightly beyond verified frontier
  -> solve with current FAP
  -> independent sandbox / holdout verification
  -> success: irreversible structural compression
  -> repeated evidence: ephemeral -> shadow -> consolidated
  -> failure: update statistics only; do not retain failed reasoning
  -> update frontier / uncertainty / stagnation
  -> select next task
```

## Ability map

The generic V81 controller can track abstract abilities such as:
- decomposition
- composition
- generalization
- verification
- repair
- creative_transfer

Each ability maintains:
- attempts and verified successes;
- success rate and EMA reward;
- current verified frontier;
- uncertainty;
- stagnation;
- a derived weakness score.

Focus selection adds an exploration bonus for untried abilities and a repetition penalty, preventing one difficult weakness from starving the rest of the curriculum.

## Difficulty control

The next task targets a point just above the verified frontier:

`next = frontier + stretch * (0.75 + uncertainty)`

As evidence accumulates, uncertainty falls and the stretch naturally tightens.

## Success-only memory

Raw reasoning traces are not persisted.

`SuccessCompressor` retains only:
- ability;
- compact structural signature;
- short summary;
- verified difficulty;
- reward;
- evidence digests.

Independent repeated evidence promotes a pattern:

`1 = ephemeral -> 2 = shadow -> 3+ = consolidated`

Duplicate evidence cannot advance promotion.

## Concrete V80 sandbox bridge

V81 includes `PrimitiveSelfCurriculum`, which directly exercises the V80 Primitive Inventor stack.

Current bounded curriculum domains are:
- `string_normalization`;
- `numeric_transform`;
- `list_transform`.

For every generated task:
1. V81 creates five training examples including a boundary case.
2. V80 `PrimitiveInventor` searches a safe Mini-IR program.
3. V80 `MiniIRSandbox` executes the candidate.
4. V80 `PrimitivePromotionLoop` evaluates all unit cases plus three unseen holdout cases.
5. Only an `active` promotion counts as a V81 learning success.
6. V81 then updates its ability map and compresses the successful pattern.

This is the first concrete path from self-generated curriculum to actual sandbox-verified FAP capability growth.

## Failure behavior

Solver or verifier exceptions are converted into failed learning observations. They increase evidence about weakness/stagnation but cannot enter success memory.

## Scope

V81 implements an autonomous curriculum policy and a real bridge to the bounded V80 primitive sandbox. It does not claim arbitrary general intelligence. Broader capability growth requires adding additional safe task generators and verifiers for reasoning domains beyond the current Mini-IR space.
