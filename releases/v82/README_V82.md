# FAP V82 — Sparse Adaptive Circuit Orchestrator

V82 turns the existing small mechanisms into a verifier-gated specialist pool rather than running every mechanism on every task.

## Specialist families

- **V79 creative operators** — reframe, analogy, inversion, combination and constraint shift.
- **V81 Local Adaptive Core** — fixed reservoir, predictive readout, bounded Hebbian overlay and verified counterexamples.
- **V80 active Mini-IR primitives** — only primitives already promoted through Sandbox tests and Shadow success evidence.

## Routing rule

A circuit must satisfy both conditions:

1. it has independent verifier evidence and is not quarantined;
2. its routing score clears the activation threshold.

Only then can it compete for the top-k slots. Default `top_k=2`. If nothing is relevant enough, zero optional circuits execute.

Routing score combines:
- task/tag similarity;
- bounded base priority;
- verified lifecycle stage;
- short-lived success-only Active Memory;
- a small bounded generation bonus.

## Evolution

A consolidated circuit may propose a few deterministic parameter mutations. A child starts as `candidate`, has no execution rights, and cannot enter routing until separately certified.

## Active Memory

Only verified successful runtime outcomes enter Active Memory. Failures do not become positive routing memories. Repeated runtime failure can quarantine and revoke a specialist.

## Primitive integration

The V80 bridge adopts only SkillRegistry records at `active`. Their recorded automatic-test, boundary, determinism, timeout and Shadow-success evidence is rechecked before V82 grants routing eligibility.

## V81 local adaptation integration

V81 local adaptation is registered as one specialist circuit. Certification confirms that a passive guidance probe does not change the fixed reservoir digest or verified-learning evidence. Its guidance runs only when the shared router actually selects the circuit.

## Combined loop

```text
Task
  → verifier-approved circuit pool
  → relevance activation threshold
  → sparse top-k selection
  → execute selected specialists only
  → verify outcome
  → success-only Active Memory
  → promote / quarantine
  → optional bounded mutation
  → new unroutable candidate
  → independent verification
```

Invention or mutation proposes a circuit. Verification grants execution rights.
