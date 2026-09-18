# Decision — V71 Interaction Runtime

Decision: KEEP for main integration review.

Independent GitHub Actions passed on Python 3.11 and 3.12 for this candidate lineage:
- V71 focused runtime tests: PASS;
- V70 provider-adapter regression: PASS;
- V69 interaction regression: PASS;
- V66 operational 28/28 PASS;
- V67 code-factory 28/28 PASS;
- V68 code-factory 34/34 PASS;
- compileall PASS.

The runtime reports provider presence as "configured", not "healthy" or "proven". Missing
image/STT/TTS providers fail closed and half-duplex voice reports the exact missing provider
set. Raw PCM is not copied into runtime metadata.

Real image generation, transcription and synthesis remain DEFER until independently exercised
concrete backends are available.

Rollback anchor: main V70 `c4a3f5d3c7a0590c7506f807ac4881b94524a5a3`.
Rollback action: remove/disable the additive V71 runtime package.
