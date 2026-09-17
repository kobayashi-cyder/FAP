# FAP Media Skill Foundation — Preparation

Baseline: current main V66. This branch is non-main and must not be promoted as a bundle without independent review.

## Goal
Provide a small, auditable contract shared by image generation, video generation, speech input, speech output, and voice-turn skills.

## Guarantees
- A skill never reports generated media when no provider/renderer is configured.
- Binary artifacts must be non-empty and carry a media MIME type.
- Artifact SHA-256 is available for evidence/provenance.
- Provider interfaces are narrow so Android/local/cloud backends can be swapped without changing the skill contract.

## Next implementation lanes
1. image generation: request validation -> render plan -> provider -> image artifact verification.
2. video generation: scene/timing plan -> renderer boundary (Remotion-compatible adapter is a candidate) -> video artifact verification.
3. audio input: PCM16 validation -> signal inspection/VAD evidence -> STT provider.
4. audio output: TTS request validation -> TTS provider -> audio artifact verification.
5. voice session: half-duplex STT -> responder -> TTS first; full-duplex/barge-in later.

## Required evidence before any main promotion
- deterministic unit tests;
- negative tests for empty/malformed artifacts and unsupported media parameters;
- provider failure/timeout behavior;
- resource measurements on representative Android/host execution;
- explicit privacy boundary for microphone/audio retention;
- no API/provider-specific secrets stored in the repository.

## Current local verification
The combined prototype suite was executed locally before upload: 12/12 unittest cases PASS. GitHub/CI verification remains required before promotion.
