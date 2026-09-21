# FAP latest development snapshot

Current mainline: **V87.13 — Bounded Iterative Media Generation**.

V87.13 adds a provider-neutral quality loop for image and video generation:

`request -> generate -> independent critic -> defect-scoped repair -> regenerate -> quality gate`

Key behavior:
- supports image and video artifacts through one bounded controller;
- preserves the user's original request across repair turns;
- retains the best verified artifact if later attempts regress;
- rejects fatal critic evidence fail-closed;
- stops stalled duplicate-output loops;
- keeps generation backends replaceable rather than coupling FAP to one model.

Verification:
- V87.13 focused tests: **7/7 PASS on Python 3.11**
- V87.13 focused tests: **7/7 PASS on Python 3.12**
- GitHub Actions run: **35586178717 — SUCCESS**
- prior V87.12 runtime suite: **91/91 PASS**

V87.13 does **not** claim a native photorealistic image generator or text-to-video diffusion model. It strengthens FAP's self-refining generation control layer so connected generators can be iteratively improved under independent evidence.

Implementation: `releases/v87_13/media_generation/`.

Promotion history is intentionally sequential through V87.13. Qwen is not used.
