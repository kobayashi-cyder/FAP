# FAP V79 — Creativity Success Learning

V79 adds a bounded creativity layer on top of V78's distilled Teacher-learning stack.

## What is new

- Five divergent operators: reframe, analogy, inversion, combination, constraint shift.
- Multi-candidate generation and recombination.
- Explicit novelty, utility, consistency and diversity scoring.
- Verified creative-experience ledger with evidence replay protection.
- Promotion lifecycle: ephemeral -> shadow -> consolidated.
- Persisted success priors that influence later operator ranking.
- Fifteen bundled mechanism-verified success observations (3 per operator).
- Clean-evaluation switch that disables bundled experience.
- V79 -> V78 -> base-responder composition so distilled guidance remains active.
- Ideas remain labelled as hypotheses/ideas and are never promoted to factual Knowledge automatically.

## What “verified success” means here

The V79 bootstrap is a mechanism validation, not a claim of human-level creativity.

A candidate is accepted only when it passes deterministic gates for:
- valid operator,
- non-empty output,
- preservation of the task,
- novelty,
- utility,
- consistency,
- diversity,
- aggregate candidate score.

Three distinct evidence IDs are required before an operator reaches consolidated state. Duplicate evidence cannot advance promotion.

## Absorption behavior

On normal V79 startup, the verified bootstrap experiences are reconstructed and absorbed into the experience ledger. Later candidate ranking is conditioned by similarity to previously successful tasks.

For clean benchmarking:

```python
CreativityEngine(use_bundled_experience=False)
```

starts with no bundled creative experience.

## Integration order

```text
user
  -> V79 creative divergence
  -> V78 distilled Teacher-learning guidance
  -> base responder
  -> answer
```

This preserves V78 distillation while adding learned creative search ahead of it.
