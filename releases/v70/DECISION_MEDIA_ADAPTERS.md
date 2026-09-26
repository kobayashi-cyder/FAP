# Decision — V70 media provider adapters

Decision: KEEP for main integration review.

Independent GitHub Actions passed on Python 3.11 and 3.12 for the implementation lineage:
- V70 provider-adapter focused tests: 12/12 PASS;
- V69 interaction regression: 11/11 PASS;
- V66 operational regression: 28/28 PASS;
- V67 code-factory regression: 28/28 PASS;
- V68 code-factory regression: 34/34 PASS;
- compileall for V70 adapters and V69 interaction: PASS.

Verified V70 behavior includes:
- absolute existing executable requirement;
- shell=False fixed-command JSON protocol;
- image/STT/TTS integration with V69 interfaces;
- deterministic fixture artifact digest;
- timeout, nonzero exit, malformed JSON, malformed artifact, request-size and response-size failures;
- sanitized process environment that does not inherit an arbitrary test secret;
- half-duplex voice through STT -> responder -> TTS adapters.

Limitations:
The CI fixture is not a real image-generation model, STT engine, or TTS engine. This release
makes those backends safely connectable but does not claim real generation/transcription/
synthesis until a concrete backend is independently exercised. Android microphone,
audio-focus, streaming, full duplex, barge-in, echo cancellation and wake-word behavior
remain DEFER.

Rollback anchor: main V69 `e338d9bb70afd7d46fd2465feaedc3d133630e6a`.
Rollback action: remove/disable the additive V70 media adapter package.
