# FAP V84 — Persistent Self-Generated Curriculum

V84 adds a persistent self-generated curriculum controller above the current V83/V82 learning and specialist stack.

The controller maintains a verified capability map, selects weak or uncertain areas, generates a task slightly above the current verified frontier, solves it with the current FAP stack, and advances capability state only after independent verification.

## Closed loop

```text
persistent AbilityMap
  -> select weak / uncertain / underexplored capability
  -> create a slightly harder challenge
  -> solve with current FAP capabilities
  -> independent verifier / holdout
  -> trusted success only: update frontier + compress reusable structure
  -> ephemeral -> shadow -> consolidated
  -> failure or non-independent result: no capability promotion
  -> persist and choose the next target
```

## V84 correctness changes

V84 incorporates the PR #37 review findings instead of copying the older V82 proposal unchanged:

- a verifier result must be both `passed=True` and `independent=True` before it can increment verified successes or advance the AbilityMap frontier;
- non-independent positive self-assessment is treated as untrusted for capability reward;
- success evidence is bound to the full generated challenge, including task id, ability, prompt, difficulty, parent pattern, novelty and payload;
- reused task IDs after restart therefore cannot collapse distinct harder challenges into the same evidence digest.

## Ability map

Each capability tracks:
- attempts;
- independently verified successes;
- success rate;
- EMA reward;
- highest verified frontier;
- uncertainty;
- stagnation;
- weakness.

Focus selection balances weakness, uncertainty, coverage of untried capabilities and repetition penalties.

## Success-only compression

Raw reasoning traces are not persisted as reusable memory. `SuccessCompressor` stores compact structural signatures, verified difficulty, reward and challenge-bound evidence digests.

Promotion remains:

`ephemeral -> shadow -> consolidated`

Distinct independently verified evidence is required.

## Concrete Mini-IR practice bridge

`PrimitiveSelfCurriculum` connects the curriculum loop to the bounded primitive stack:

`Primitive Inventor -> Mini-IR Sandbox -> Skill Registry -> Promotion Loop`

Current generated exercises cover:
- string normalization;
- numeric transforms;
- list transforms.

Each exercise includes five training examples, boundary coverage and three unseen holdouts. A curriculum result counts as success only when the primitive promotion loop reaches `active`.

## Relationship to V83

V83 remains the bidirectional Visual IR cognition layer. V84 is an upper-level learning-policy layer and does not replace Visual IR, sparse routing, local adaptation, creativity or teacher-derived bounded priors.

## Boundary

V84 determines what to practice next and when a verified capability frontier may advance. It does not fabricate competence and does not permit arbitrary generated code execution.
