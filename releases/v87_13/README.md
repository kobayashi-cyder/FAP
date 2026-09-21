# FAP V87.13 — Bounded Iterative Media Generation

V87.13 adds a provider-neutral quality-control loop for image and video generation.

Core loop:

`request -> generate -> independent critic -> defect-scoped repair prompt -> regenerate -> quality gate`

What is new:
- the same bounded controller supports image and video artifacts;
- the user's original subject/request remains authoritative on every repair turn;
- independent critique evidence controls acceptance;
- fatal critique evidence fails closed;
- repeated identical artifacts terminate a stalled loop;
- the best verified artifact is retained even if later attempts regress;
- attempt count and score gates are bounded;
- generation backends remain replaceable.

This is **not** a claim that FAP now contains a photorealistic image model or a text-to-video diffusion model. V87.13 improves FAP's ability to drive and refine connected generation backends until a measurable quality gate is met.

Verification target: `releases/v87_13/media_generation/tests`.
