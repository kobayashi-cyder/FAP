# Voice Conversation Skill — PREP

Status: non-main experimental lane.

## Guaranteed scope now
- Half-duplex single turn only: validated PCM16 -> STT -> text responder -> TTS -> verified audio artifact.
- Propagates `needs_provider` rather than pretending STT/TTS succeeded.
- Records transcript, response text and output-audio digest as turn evidence.

## Deliberately deferred skills
1. streaming partial STT;
2. full-duplex simultaneous listen/speak;
3. barge-in/interruption;
4. acoustic echo cancellation;
5. jitter buffer and packet-loss handling;
6. wake-word/hotword gating;
7. speaker/voice activity state machine;
8. privacy-controlled conversation recording/retention.

Each deferred item should be its own tested sub-skill rather than hidden inside one monolithic voice loop.

## Next implementation steps
- Add explicit turn/session IDs and monotonic state transitions.
- Add cancellation/timeouts around STT, responder and TTS.
- Add streaming interface while retaining this single-turn path as regression baseline.
- Add Android AudioRecord/AudioTrack adapter behind interfaces.
- Add echo/barge-in only after real-device fixtures exist.

## Promotion evidence
- STT/TTS unavailable and timeout paths;
- empty responder output rejection;
- cancellation between phases;
- deterministic session-state tests;
- no raw microphone retention by default;
- Android permission, audio focus, interruption and speaker/mic lifecycle tests;
- latency budget measured separately for STT, reasoning and TTS.

Local combined prototype suite before upload: 12/12 PASS. Full real-time voice conversation is not claimed by this branch yet.
