# FAP latest development snapshot

Current mainline: **V87.14 — Temporal Consistency Critic**.

V87.14 extends V87.13's bounded iterative media generation with independent video-temporal verification.

Current media loop:

`request -> generate -> observe actual artifact -> temporal critic -> defect-scoped repair -> regenerate -> quality gate`

V87.14 detects:
- subject identity / appearance drift across sampled frames;
- implausible frame-to-frame motion jumps;
- expected-subject dropout;
- large adjacent-frame luminance flicker;
- malformed, dimension-changing, or non-monotonic temporal evidence.

Fail-closed behavior:
- video output without actual temporal evidence is not accepted by the temporal critic;
- invalid time evidence becomes a fatal critique;
- temporal defects are converted to bounded repair hints that V87.13 can feed back to a connected video generator.

Verification:
- V87.14 focused tests: **8/8 PASS on Python 3.11**
- V87.14 focused tests: **8/8 PASS on Python 3.12**
- GitHub Actions run: **35586419196 — SUCCESS**
- V87.13 media-generation tests remain the preceding verified layer.
- prior V87.12 runtime suite: **91/91 PASS**

V87.14 does **not** claim native text-to-video synthesis, video decoding, optical flow, or face recognition. Those remain replaceable generator/observer backends. The new capability is independent temporal consistency verification and repair signaling.

Implementation:
- `releases/v87_13/media_generation/`
- `releases/v87_14/video_temporal/`

Promotion history is intentionally sequential through V87.14. Qwen is not used.
