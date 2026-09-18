# Decision — V70 media provider adapters

Current decision: MODIFY / pending independent CI.

Implementation is additive and intentionally does not claim a real renderer/STT/TTS backend.
Promotion requires same-HEAD Python 3.11/3.12 CI and current core regression evidence.

Rollback anchor: main V69 `e338d9bb70afd7d46fd2465feaedc3d133630e6a`.
