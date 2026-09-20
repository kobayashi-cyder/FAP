# FAP V80 — Sparse Adaptive Circuits

V80 is an additive layer on top of V79 Creativity Success Learning. It does not replace the existing creativity or teacher-learning mechanisms.

## Added

- **Verifier First execution rights**: an uncertified or quarantined circuit cannot enter the runtime route.
- **Sparse routing**: by default only the top 2 verified specialist circuits are activated per task.
- **Active success memory**: only verified successful traces are retained as short-lived routing priors; failed/unverified traces are excluded from active memory.
- **Bounded circuit evolution**: consolidated circuits can emit deterministic mutated children. Children start as `candidate` and cannot run until separately benchmark-certified.
- **Promotion**: verified successes move `candidate -> ephemeral -> shadow -> consolidated`.
- **Failure quarantine**: repeated verified failures revoke execution eligibility.
- **V79 creativity binding**: the five V79 operators become specialist circuits and only routed operators render at runtime.
- **V78 composition**: `build_v80_responder()` preserves teacher-learning guidance before the base responder.

## Runtime loop

```text
Task
  -> Verifier-approved circuit pool
  -> Sparse Router (top-k)
  -> Execute selected circuits only
  -> Verify outcome
  -> Success-only Active Memory
  -> Promotion / quarantine
  -> optional circuit mutation
  -> candidate child
  -> sandbox/benchmark certification
  -> eligible routing pool
```

The important constraint is that evolution never grants itself execution rights. Mutation proposes structure; verification grants execution.
