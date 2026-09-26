# Decision — V74 Health-gated Runtime

Decision: KEEP for main integration review.

Independent GitHub Actions passed on Python 3.11 and 3.12:
- V74 focused health-gate tests: PASS;
- V73 provider-probe regression: PASS;
- V72 audio-lifecycle regression: PASS;
- V71 interaction-runtime regression: PASS;
- V70 provider-adapter regression: PASS;
- V69 interaction regression: PASS;
- V66 operational 28/28 PASS;
- V67 code-factory 28/28 PASS;
- V68 code-factory 34/34 PASS;
- compileall PASS.

Verified behavior:
- chat remains usable without any media probe;
- unprobed/unhealthy/incompatible/undeclared media paths are blocked before provider invocation;
- unconfigured providers remain needs_provider;
- healthy declared capabilities invoke the existing V71/V70 path;
- half-duplex voice requires both STT and TTS declarations.

Limitations:
This is execution gating, not proof of real media quality. Real image generation/STT/TTS
claims still require independently exercised concrete backends.

Rollback anchor: main V73 `86b4c04f90f3c6495ef3190d361bb33a7068acf4`.
