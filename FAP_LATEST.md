# FAP latest development snapshot

Current additive development release: **V69 — Chat + Image + Audio Interaction Surface**.

Source, tests, preparation notes and decision records are stored under [`releases/v69/`](releases/v69/).

V69 adds an additive interaction layer on top of V68:
- bounded chat sessions with `:brief`, `:normal`, `:rich`, and `:verbose` modes;
- a provider-neutral image-generation boundary with request, MIME, non-empty artifact and SHA-256 validation;
- validated PCM16 audio input with an STT provider boundary;
- validated TTS output with audio artifact verification;
- a half-duplex voice turn: STT -> responder -> TTS;
- fail-closed behavior for missing providers, timeouts, provider errors, wrong MIME types, empty artifacts, and empty transcripts.

Independent GitHub Actions verification on the candidate HEAD passed on Python 3.11 and 3.12. The gate included the focused V69 interaction suite, compileall, V66 operational 28/28, V67 code-factory 28/28, and V68 code-factory 34/34.

**Important limitation:** V69 supplies the mainline interaction contracts and verified provider boundaries. It does not bundle or claim a concrete production image model, STT engine, or TTS engine. Real provider-backed generation/transcription/synthesis requires a separately verified adapter. Full-duplex voice, barge-in, echo cancellation, wake word, and streaming remain deferred.

V68 TaskPlan AST Repair + Candidate Race Code Factory remains intact underneath this additive interaction surface.
