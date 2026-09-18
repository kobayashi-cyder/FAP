# TEST PREP — V72 Audio Lifecycle

Required:
- complete happy-path half-duplex state progression;
- permission denied and audio-focus denied;
- invalid listen-while-speaking transition;
- focus-loss cancellation;
- permission-revocation cancellation during listening/transcribing;
- cancellation then clean restart;
- reset clears transient metrics;
- negative metrics rejected;
- snapshot asserts no raw PCM/transcript/response text retention;
- compileall;
- V71/V70/V69 regressions and V66-V68 core regressions;
- same-HEAD Python 3.11/3.12 independent CI.

Android permission APIs, AudioRecord, AudioManager/audio focus, real microphone/speaker,
full duplex, barge-in, echo cancellation, wake word and streaming remain separate evidence.
