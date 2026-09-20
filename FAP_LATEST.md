# FAP latest development snapshot

Current additive development release: **V80 — Sparse Adaptive Circuits**.

Source, tests and integration notes are stored under [`releases/v80/`](releases/v80/).

V80 is additive on top of V79 Creativity Success Learning and V78 Gemma 4 Direct-Learning Integration. It preserves the existing creativity operators, verified creative-experience lifecycle, teacher-shadow memory and concept graph while adding a verifier-gated adaptive circuit layer.

V80 adds:
- verifier-first execution rights: uncertified or quarantined circuits cannot enter runtime routing;
- sparse top-k specialist routing, defaulting to two circuits per task;
- bounded success-only Active Memory used as a routing prior;
- deterministic bounded circuit mutation for consolidated parents;
- strict child lifecycle: mutated children begin as unroutable `candidate` circuits;
- `candidate -> ephemeral -> shadow -> consolidated` promotion on verified successes;
- automatic quarantine and eligibility revocation after repeated failures;
- V79 creativity operator binding so only routed creative operators render at runtime;
- V78 teacher-learning composition through `build_v80_responder()`.

Local Python 3.11 checks passed for the V80 core (compile + 10/10 unit tests). Repository CI verifies V80 on Python 3.11 and 3.12 and runs V79/V78/V75/V71 regressions.

**Important limitation:** V80 evolves specialist selection and bounded routing/circuit parameters. It does not yet auto-synthesize arbitrary executable circuit code. Generated executable implementations must remain behind the existing Primitive Inventor -> Sandbox -> Registry verification path before receiving execution rights.
