# FAP latest development snapshot

Current additive development release: **V81 — Local Adaptive Predictive Core**.

Source, tests and integration notes are stored under [`releases/v81/`](releases/v81/).

V81 is additive on top of the current mainline, including the V80 Primitive Inventor / Mini-IR sandbox / Skill Registry promotion loop and the V79 creativity-success learning stack. It adds a verifier-gated local adaptation layer without replacing those systems.

V81 adds:
- deterministic compact text encoding;
- a sparse mostly-fixed recurrent reservoir;
- next-input predictive coding that learns prediction error at the readout;
- a small bounded Hebbian plastic overlay applied only after verified success;
- verified counterexample memory for failure-pattern avoidance;
- action-sensitive counterexample penalties;
- replay protection for all verified learning evidence;
- passive runtime observation that never silently changes learning weights;
- SHA-256 protected JSON persistence with fail-closed restoration;
- V81 -> V79 responder composition while preserving current V80 primitive-invention capability and V78 teacher-learning guidance.

The fixed reservoir is not globally retrained. Learning is restricted to the predictive readout, a bounded sparse local overlay, and verified negative-experience memory.

**Important limitation:** V81 verifies a cheap local-learning mechanism. It does not by itself create LLM-level language ability. Weight-changing updates remain verifier-gated, and counterexamples remain negative experience rather than successful skill memory.
