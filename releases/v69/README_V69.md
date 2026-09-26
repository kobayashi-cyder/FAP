# FAP V69 — Chat + Image + Audio Interaction Surface

V69 promotes a small, provider-neutral interaction surface to main while preserving the V68 code-factory and V66 verification stack.

## Added

### Chat
- bounded recent-turn state;
- `:brief`, `:normal`, `:rich`, `:verbose` modes;
- explicit empty-input / empty-response rejection;
- responder remains replaceable rather than being hard-wired to one language model.

### Image
- validated prompt, dimensions, format and optional seed;
- provider-neutral image interface;
- non-empty artifact validation;
- MIME validation including requested-format matching;
- SHA-256 artifact digest;
- explicit `needs_provider` when no renderer is configured;
- fail-closed timeout and provider-error paths.

### Audio input
- PCM16 byte alignment, sample-rate and channel validation;
- RMS / speech-likelihood inspection;
- provider-neutral STT boundary;
- empty transcript rejection;
- timeout/error handling;
- raw PCM is not copied into result metadata.

### Audio output
- bounded non-empty text, voice and sample-rate validation;
- provider-neutral TTS boundary;
- non-empty audio artifact and MIME validation;
- SHA-256 audio digest;
- timeout/error handling.

### Voice
- half-duplex baseline only:
  `PCM16 -> STT -> responder -> TTS -> verified audio artifact`.

## Explicitly deferred

V69 does **not** claim a bundled real image-generation model, STT engine, or TTS engine.
A concrete adapter must be independently exercised before such a claim is made.

The following voice features also remain separate future work:
- full duplex;
- barge-in;
- acoustic echo cancellation;
- wake word;
- streaming partial STT/TTS.

## Validation

Independent GitHub Actions passed on Python 3.11 and Python 3.12:
- V69 focused interaction tests: PASS;
- V69 compileall: PASS;
- V66 operational regression: 28/28 PASS;
- V67 code-factory regression: 28/28 PASS;
- V68 code-factory regression: 34/34 PASS.

A broader historical suite also exposed an existing environment-sensitive RSS-source assertion in the V68 baseline. V69 does not modify `releases/v68/**`; this issue remains recorded rather than hidden by weakening tests.

## Rollback

Rollback anchor: V68 main `929c419b3fcff55720e159b8f7f7f1d602dec305`.

V69 is additive and can be disabled/removed without migrating V68 state.
