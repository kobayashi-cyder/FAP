# FAP V87.14 — Temporal Consistency Critic

V87.14 extends V87.13's iterative media-generation loop with independent structured video evidence.

It detects:
- identity/appearance drift for the same tracked subject;
- implausible frame-to-frame motion jumps;
- expected-subject dropout;
- large adjacent-frame luminance flicker;
- invalid/non-monotonic temporal evidence.

The critic is fail-closed when actual frame evidence is missing or malformed.

Production contract:
1. generate a video through a connected provider;
2. observe the actual generated artifact and sample frames;
3. attach bounded frame/object evidence to the video artifact;
4. run TemporalConsistencyCritic;
5. feed verified defects into V87.13's defect-scoped regeneration loop.

This release does **not** claim native video decoding, optical flow, face recognition, or text-to-video synthesis. Those remain replaceable observer/generator backends. The improvement is the temporal verification and repair signal that FAP can use independently of any one provider.
