# FAP V81 — Local Adaptive Predictive Core

V81 adds a small verifier-gated learning loop in front of V79.

## Core idea

The internal recurrent circuit is mostly fixed. FAP learns only what is useful:

1. encode the current input,
2. run it through a deterministic sparse reservoir,
3. predict the next input,
4. learn the prediction difference at the readout,
5. apply a tiny bounded Hebbian overlay only after verified success,
6. store verified failures as counterexamples,
7. penalize similar future action patterns.

This is deliberately different from retraining a large model.

## Components

### Predictive coding

`PredictiveReadout` predicts the next compact input vector from reservoir state. Learning uses prediction error only.

Runtime calls are passive: normal conversation does not silently train the weights. Training requires `learn_transition(..., verified=True, evidence_id=...)`.

### Fixed reservoir

`FixedReservoir` uses deterministic sparse input and recurrent weights. Their SHA-256 digest is stable across local learning.

Only a small `plastic_overlay` may change.

### Local Hebbian plasticity

`LocalHebbianOverlay` updates only strongly co-active local edges after verified success.

Bounds:
- maximum local edge magnitude: 0.16,
- maximum plastic edges: 96,
- fixed reservoir remains unchanged.

### Counterexample learning

`CounterexampleMemory` stores verified failure patterns instead of treating them as successful procedures.

Future similar inputs receive a similarity-based penalty. A sufficiently similar verified failure adds an avoidance hint to the downstream context.

### Replay protection

Every verified learning event requires a unique `evidence_id`. Replaying the same evidence is rejected before any readout or Hebbian mutation.

### Persistence

The learned state can be saved as JSON:
- predictive readout,
- local plastic overlay,
- verified evidence IDs,
- counterexamples.

The envelope is SHA-256 protected and loading fails closed on tampering, wrong dimensions, wrong fixed reservoir digest, malformed edges, or unsupported schema.

## Integration order

```text
user
  -> V81 local adaptation
  -> V79 creative search
  -> V78 teacher-learning guidance
  -> base responder
  -> answer
```

V81 does not take final-answer authority away from the lower stack.

## Intended learning API

```python
result = core.learn_transition(
    source_text="画面が切り替わる",
    target_text="元のアプリを呼び戻す",
    evidence_id="run-20260920-001",
    verified=True,
    success=True,
    action_tag="navigation",
)
```

For a verified failure:

```python
core.learn_transition(
    source_text="同じボタンを無限連打",
    target_text="停止",
    evidence_id="run-20260920-fail-001",
    verified=True,
    success=False,
    action_tag="rapid_tap",
    failure_severity=1.0,
)
```

The failure updates predictive knowledge of what happened, does not receive Hebbian success reinforcement, and is stored as a counterexample.

## Scope

V81 validates the mechanism. It does not claim that a small reservoir alone provides LLM-level language ability. Its purpose is to make FAP's existing circuits adapt cheaply and locally while preserving verifier-first control.
