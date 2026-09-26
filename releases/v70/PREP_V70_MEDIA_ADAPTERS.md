# V70 candidate — Trusted local media provider adapters

Status: implementation candidate, non-main.
Base: main V69 `e338d9bb70afd7d46fd2465feaedc3d133630e6a`.

The earlier Deterministic Replay V70 roadmap remains advisory. User priority now favors
making the V69 chat/image/audio surface practically connectable, so this candidate uses V70
for a small trusted local provider adapter layer instead of merging the stale replay branch.

## Scope
- fixed absolute provider executable;
- fixed argument prefix;
- shell=False subprocess execution;
- canonical JSON request protocol;
- timeout and request/response size limits;
- sanitized environment with no arbitrary secret inheritance;
- command adapters for image, STT, and TTS;
- direct integration with V69 ImageGenerationSkill, AudioInputSkill, AudioOutputSkill,
  and half-duplex VoiceConversationSkill.

## Security boundary
This is a trusted local adapter mechanism, not an arbitrary command runner. Provider
configuration must be supplied by trusted application configuration. User text is serialized
as JSON stdin and is never interpolated into a shell command.

## Non-claims
The committed CI fixture is not a real image model, STT engine, or TTS engine. It proves the
adapter protocol and failure handling. Real generation/transcription/synthesis still requires
one concrete backend to be independently exercised on its target platform.

## Promotion
Require focused adapter tests and V69/V68 core regression on the same HEAD. Rollback is
removal/disable of the additive V70 adapter package.
