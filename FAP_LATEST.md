# FAP latest development snapshot

Current mainline: **V87.15 — Observed Media Refinement Host**.

V87.15 closes the generation-to-observation wiring gap across image/video refinement.

Current media loop:

`request -> generate -> observe actual artifact -> digest-bind evidence -> critics -> defect-scoped repair -> regenerate -> quality gate`

New in V87.15:
- every generated artifact is observed before critique;
- observer evidence is bound to the exact generated artifact digest;
- stale or cross-artifact evidence fails closed;
- observers can be scoped independently to image or video artifacts;
- multiple critics compose fail-closed using the minimum score;
- a strong aesthetic score cannot hide a fatal temporal/structural critic;
- original generator metadata is preserved alongside observation evidence.

Verification:
- V87.15 focused tests: **8/8 PASS on Python 3.11**
- V87.15 focused tests: **8/8 PASS on Python 3.12**
- GitHub Actions run: **35586649662 — SUCCESS**
- V87.14 temporal critic tests: **8/8 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

V87.15 does **not** claim a native photorealistic image generator, native text-to-video generator, video decoder, optical-flow model, or identity model. Those remain replaceable organs. The new capability is a verified host that forces each generation attempt through observation and digest-bound evidence before acceptance.

Implementation:
- `releases/v87_13/media_generation/`
- `releases/v87_14/video_temporal/`
- `releases/v87_15/observed_media/`

Promotion history is intentionally sequential through V87.15. Qwen is not used.
