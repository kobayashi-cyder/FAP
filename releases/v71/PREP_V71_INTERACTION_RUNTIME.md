# V71 candidate — Interaction Runtime Capability Router

Status: implementation candidate, non-main.
Base/rollback anchor: main V70 `c4a3f5d3c7a0590c7506f807ac4881b94524a5a3`.

The older replay-oriented V71 prep is stale and non-binding. Current user priority is
practical chat/image/audio capability.

## Scope
- one runtime facade for chat/image/STT/TTS/half-duplex voice;
- capability reporting that distinguishes configured from proven/healthy;
- fail-closed missing-provider routing;
- bounded chat through the existing V69 ChatSession;
- no raw PCM copied into runtime result metadata.

## Non-claims
Configured providers are not automatically described as healthy. Real image generation,
transcription, and synthesis still require independently exercised concrete backends.

## Promotion
Require focused V71 tests, V70 adapter regression, V69 interaction regression, V66-V68 core
regressions, compileall, and same-HEAD CI on Python 3.11/3.12.
