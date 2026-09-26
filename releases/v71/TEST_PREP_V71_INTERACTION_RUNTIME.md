# TEST PREP — V71 Interaction Runtime

Required:
- capability report with no providers;
- chat operation without media providers;
- chat mode commands;
- image/STT/TTS missing-provider behavior;
- successful fixture-backed image/STT/TTS paths;
- exact missing provider list for half-duplex voice;
- no raw PCM in runtime metadata;
- successful half-duplex voice with STT+TTS configured;
- compileall;
- V70 adapter, V69 interaction, and V66-V68 core regressions;
- Python 3.11/3.12 independent CI.

Real provider claims remain DEFER until a concrete backend is independently exercised.
