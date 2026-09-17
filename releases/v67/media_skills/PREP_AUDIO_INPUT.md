# Audio Input / Speech-to-Text Skill — PREP

Status: non-main experimental lane.

## Guaranteed scope
- Accept validated PCM16 only.
- Validate sample rate and channel count.
- Expose simple RMS/speech-likelihood evidence before transcription.
- Refuse to claim transcription when no STT provider exists.
- Reject empty transcripts from a provider.

## Next implementation steps
1. Streaming chunk assembler with bounded buffer.
2. Better VAD with hysteresis and silence timeout.
3. Timestamped transcript segments and confidence fields.
4. Android microphone adapter with explicit permission/privacy boundary.
5. Provider timeout/retry/cancellation and offline/local STT adapter candidate.

## Promotion evidence
- malformed PCM/channel/sample-rate tests;
- silence/noise/speech fixture tests;
- streaming boundary and dropped-chunk tests;
- STT timeout/error/empty-result tests;
- microphone data retention policy and redaction rules;
- latency/RAM/battery measurements on representative Android hardware.

Local combined prototype suite before upload: 12/12 PASS. Real microphone/STT integration remains separate evidence.
