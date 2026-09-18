# Voice Session — current-main preparation addendum

Reviewed against main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

Baseline remains half-duplex only: capture -> STT adapter -> FAP responder boundary -> TTS adapter -> playback. Session orchestration must not imply that STT/TTS exists when either concrete adapter is absent. Test missing provider(s), STT/TTS timeout/error, empty transcript/audio, cancellation at every state, duplicate callback, stale turn result and deterministic state transitions.

Android: require RECORD_AUDIO handling, mic release before/while playback as defined, audio-focus acquire/loss/abandon, lifecycle stop/background cleanup and no hidden continuous capture. User audio/transcripts are ephemeral by default; synthetic fixtures for evidence. Measure turn latency split by capture/STT/FAP/TTS/playback setup, peak RAM and retained bytes.

Promotion requires independently exercised STT and TTS adapters and end-to-end half-duplex evidence against current main. DEFER full-duplex, barge-in, echo cancellation, wake-word and streaming until separate tests prove them. REPLACE orchestration if sibling interfaces converge on a better typed session contract; never bundle sibling branches automatically.