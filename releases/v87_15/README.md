# FAP V87.15 — Observed Media Refinement Host

V87.15 closes the wiring gap between generation and critique.

Before V87.15:
- V87.13 could iteratively regenerate based on critic feedback.
- V87.14 could critique temporal evidence.
- A caller still had to manually observe each generated artifact and attach the right evidence.

V87.15 adds an observed-media host:

`generate -> observe actual artifact -> digest-bind evidence -> critics -> bounded repair -> regenerate`

Properties:
- every generation attempt is independently observed before critique;
- evidence is accepted only when bound to the exact generated artifact digest;
- stale/cross-artifact evidence fails closed;
- observers can be scoped to image or video artifacts;
- multiple critics compose fail-closed using the minimum score;
- a strong aesthetic score cannot mask a fatal structural/temporal critic;
- generator metadata is preserved while observation evidence is attached.

This release is provider-neutral. It does **not** claim a native photorealistic generator, native video decoder, optical flow engine, or identity model. Instead, it makes those replaceable organs usable inside one verified FAP refinement loop.
