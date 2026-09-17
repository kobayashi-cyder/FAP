# Audio Output / Text-to-Speech Skill — PREP

Status: non-main experimental lane.

## Guaranteed scope
- Validate non-empty bounded text, voice identifier and output sample rate.
- Refuse to claim synthesis when no TTS provider exists.
- Verify provider output is non-empty audio media and expose SHA-256 evidence.

## Next implementation steps
1. Add chunking for long text with sentence-boundary preservation.
2. Add streaming playback contract and cancellation.
3. Add Android audio-output adapter and focus/ducking policy.
4. Add local/offline TTS adapter candidate and provider timeout taxonomy.
5. Add loudness/peak/duration metadata checks before playback.

## Promotion evidence
- empty/oversized text and unsupported-rate tests;
- provider timeout/wrong-MIME/empty-artifact tests;
- deterministic chunking tests;
- interruption/cancellation tests;
- latency/RAM/battery measurements and safe volume/focus behavior on Android.

Local combined prototype suite before upload: 12/12 PASS. Real TTS/playback support is not claimed until a concrete adapter is independently verified.
