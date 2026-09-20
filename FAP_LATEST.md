# FAP latest development snapshot

Current additive development release: **V78 — Gemma 4 Direct-Learning Integration**.

Source, verified learning-state data, tests and integration notes are stored under [`releases/v78/`](releases/v78/).

V78 is built on the current `main` baseline `3dc56198ed2c1a5fa59b4a8e3a93c0594a0d37be`, which already contains additive releases through V77. It moves the completed Gemma 4 direct-learning result out of the historical V54 overlay and into the current FAP stack.

V78 adds:
- SHA-256-verified loading of the compact Gemma 4 learned state;
- 10 consolidated behaviour circuits;
- 22 teacher-derived memory items retained as `teacher_shadow`, not silently promoted to factual Knowledge;
- 28 concept nodes and 27 concept edges;
- deterministic circuit activation, shadow-memory retrieval and context augmentation;
- `LearnedManagedChat` integration with V75 bounded chat;
- V71 `InteractionRuntime` integration through `build_interaction_runtime()`;
- fail-closed digest validation and tamper tests.

The V69–V77 interaction, lifecycle, provider-probe, health-gating, managed-chat, Android packaging and image-HTTP layers remain additive and unchanged underneath/alongside V78.

**Important limitation:** V78 integrates distilled state and procedural circuits. It does not copy Gemma 4 neural weights into FAP and does not claim Gemma 4 or GPT-class general capability. Teacher-derived factual-looking memory remains explicitly shadow-labelled until independently verified.
