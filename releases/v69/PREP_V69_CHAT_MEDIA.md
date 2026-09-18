# V69 candidate — Chat + Image + Audio Interaction Surface

Status: implementation candidate, non-main.
Base: main V68 `929c419b3fcff55720e159b8f7f7f1d602dec305`.

This candidate reflects the current user priority: move a small set of chat functions,
image generation plumbing, speech input, speech output, and half-duplex voice toward main.
The older Android-provenance V69 plan remains advisory and is deferred rather than silently merged.

## Scope
- bounded chat session with :brief / :normal / :rich / :verbose modes;
- provider-neutral image generation contract;
- validated PCM16 speech input and STT boundary;
- validated TTS output and audio artifact boundary;
- half-duplex STT -> responder -> TTS voice turn;
- content digest for generated image/audio artifacts;
- fail-closed missing-provider, timeout, wrong-MIME, empty-artifact behavior.

## Non-claims
No real image model, STT engine, or TTS engine is bundled by this candidate.
Actual generation/transcription/synthesis is claimed only after a concrete adapter is
independently exercised. Full duplex, barge-in, echo cancellation, wake word, and streaming
are not included.

## Promotion condition
Focused tests + compileall + current V68 regression + independent CI on the same HEAD.
No API secrets. No raw microphone retention by default. Rollback is removal of the additive
`releases/v69/interaction` surface.
