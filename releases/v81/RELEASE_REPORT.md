# V81 Release Report — Local Adaptive Predictive Core

## Implemented

- deterministic signed-hash text encoder;
- sparse fixed recurrent reservoir;
- next-input predictive readout;
- prediction-error learning;
- bounded local Hebbian overlay;
- verified counterexample memory;
- action-sensitive failure penalty;
- verified-learning evidence replay rejection;
- passive runtime mode with no silent weight training;
- SHA-256 protected JSON persistence;
- V81 -> V79 -> V78 stack composition.

## Verification targets

The V81 suite checks:

- deterministic encoding;
- fixed reservoir digest stability;
- repeated verified transition learning reduces prediction error;
- unverified events cannot mutate learning state;
- local plasticity remains sparse and bounded;
- failures do not receive Hebbian reward;
- counterexamples are action-sensitive;
- duplicate verified evidence is rejected before mutation;
- passive conversation steps do not train;
- similar failures produce avoidance guidance;
- persistence round-trip;
- tampered state fails closed;
- base responder retains answer authority;
- V81 composes with V79 creativity and V78 teacher-learning guidance.

## Design boundary

The fixed recurrent circuit is intentionally not optimized by global backpropagation. V81 changes only the readout and a small sparse local overlay.

Counterexamples are stored as verified negative experience rather than being promoted to successful skill memory.
