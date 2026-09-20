# FAP latest development snapshot

Current additive development release: **V80 — Local Adaptive Predictive Core**.

Source, tests and integration notes are stored under [`releases/v80/`](releases/v80/).

V80 is additive on top of V79 Creativity Success Learning. It preserves the V79 creative-experience layer and V78 teacher-learning stack while adding a verifier-gated local adaptation layer designed for cheap incremental learning.

V80 adds:
- deterministic compact input encoding;
- a sparse mostly-fixed recurrent reservoir;
- next-input predictive coding that learns prediction error at the readout;
- a small bounded Hebbian plastic overlay applied only after verified success;
- verified counterexample memory for failure-pattern avoidance;
- action-sensitive counterexample penalties;
- replay protection for verified learning evidence;
- passive runtime observation that never silently trains;
- SHA-256 protected JSON persistence with fail-closed restoration;
- V80 -> V79 -> V78 -> base-responder composition.

The fixed reservoir weights are not globally retrained. Learning is restricted to the predictive readout, a bounded sparse local overlay, and verified failure memory.

**Important limitation:** V80 verifies a local-learning mechanism; it does not establish LLM-level language ability by itself. The verifier remains the gate for weight-changing learning, and counterexamples remain negative experience rather than successful skill memory.
