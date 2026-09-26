# Public FAP 1.0.01 Integration Track — 2026-09-26

This branch is the merge-preparation surface for the public FAP reset line.

Base:
- `side/1.0.01-dynamic-sparse-routing` (PR #163)

Integrated here:
- dynamic-sparse 1.0.01 candidate;
- r001 malformed/non-finite input hardening;
- reset-line-aware release/version contract;
- public gap audit and promotion policy.

Rules:
1. `main` is not written directly from lateral work.
2. Legacy V87/V88 history is not treated as a release number source.
3. New capability ports must branch from this integration track so they inherit the same VERSION, launchers and release checks.
4. A port may not silently replace `VERSION`, `FAP_LATEST.md`, current launchers or the 1.0.01 gateway.
5. Capability claims stay evidence-gated.
6. Every port must have focused tests and must preserve the dynamic-sparse and r001 regression gates.

Prepared descendant ports:
- speech: `side/public-1.0.01-speech-port-20260926`
- Android voice: `side/public-1.0.01-android-voice-port-20260926`
- r002 reasoning/evaluation: `side/public-1.0.01-r002-port-20260926`

Promotion order:
1. integration contract + r001 hardening;
2. independent speech layer;
3. Android adapter after its base paths are verified against the integration tree;
4. r002 reasoning/evaluation only after randomized generalization gate and full sweep are green.
