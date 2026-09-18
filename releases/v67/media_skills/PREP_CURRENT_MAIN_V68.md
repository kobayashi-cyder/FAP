# Audio Output Skill — current-main preparation addendum

Reviewed against main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

Next safe step: deterministic TTS request validation with actual synthesis behind `TTSAdapter`. Test missing provider, timeout/error, empty bytes, wrong MIME/codec, invalid sample metadata, oversized text and digest mismatch. Do not claim synthesis until a concrete adapter is independently exercised and decoded audio is verified.

Android: isolate playback from synthesis; test audio-focus acquire/loss/abandon, stop/cancel and background lifecycle without changing package behavior. Generated audio is ephemeral unless explicitly saved. Do not persist user text/provider secrets in evidence. Measure synthesis latency, bytes/sec, peak RAM and bounded text/audio duration.

Promotion requires reproducible TTS adapter evidence plus current-main regression. DEFER streaming TTS, mixing and advanced focus policy. REPLACE if a proven common media artifact/provider contract supersedes this boundary.