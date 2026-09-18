# FAP latest development snapshot

Current additive development release: **V69 — Chat, Image, and Audio Interaction Surface**.

Source, tests, preparation notes, and integration evidence are stored under
[`releases/v69/`](releases/v69/).

V69 adds an additive interaction layer on top of V68:
- bounded chat sessions with `:brief`, `:normal`, `:rich`, and `:verbose` modes;
- provider-neutral image-generation requests with non-empty/MIME/digest verification;
- validated PCM16 audio input and a speech-to-text provider boundary;
- validated text-to-speech output and audio artifact verification;
- a half-duplex voice turn: STT -> responder -> TTS;
- fail-closed handling for missing providers, timeouts, provider errors, wrong MIME, empty artifacts, and empty transcripts.

Independent GitHub Actions for the V69 candidate passed on Python 3.11 and 3.12.
The same verification run also passed the V66 operational 28/28, V67 code-factory
28/28, and V68 code-factory 34/34 core regression suites.

Important limitation: V69 provides the verified interaction/provider boundary, not a bundled
real image model, STT engine, or TTS engine. Real generation/transcription/synthesis must not
be claimed until a concrete adapter is independently exercised. Full duplex, barge-in, echo
cancellation, wake word, and streaming voice remain outside the V69 baseline.

V68 TaskPlan/AST repair and candidate-race code-factory behavior remains available beneath
this additive interaction layer. FAP remains an experimental compact cognitive architecture,
not a GPT-class pretrained language model.

Project continuation context from the ChatGPT development session is stored in
[`FAP_DEVELOPMENT_CHAT_CONTEXT.md`](FAP_DEVELOPMENT_CHAT_CONTEXT.md).
