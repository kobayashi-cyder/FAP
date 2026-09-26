# TEST PREP — V70 trusted local media provider adapters

Required:
- absolute/missing executable rejection;
- shell-free successful image/STT/TTS fixture integration;
- deterministic artifact digest for repeated fixture input;
- timeout and nonzero-exit failure;
- malformed JSON and malformed artifact schema rejection;
- request and response size limits;
- arbitrary environment secret is not inherited;
- raw PCM bytes are not copied into result metadata;
- half-duplex V69 voice turn through command adapters;
- Python 3.11 and 3.12 independent CI;
- V69 interaction regression;
- V66/V67/V68 core regression.

DEFER real-provider claims until a concrete renderer/STT/TTS backend is independently
exercised. DEFER Android microphone/audio-focus/full-duplex claims to Android-specific tests.
