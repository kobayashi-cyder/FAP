# Decision — V76 Android Python Packaging

Current decision: KEEP.

Independent verification: GitHub Actions run `35305193843` completed successfully for candidate commit `19c91c48318666a6116fec3664646828efdb7ff9` on Python 3.11 and 3.12. The workflow exercised packaging unit tests, actual-manifest sync/compile, V69–V75 focused regressions, and V66–V68 core regressions.

Scope: KEEP applies to the deterministic Android interaction-package sync layer only. It does **not** claim real image generation, STT, TTS, full-duplex audio, barge-in, echo cancellation, wake-word, or streaming capability.

Limitation: a post-promotion Android APK build is still required when/if this candidate is integrated; main is intentionally untouched by this branch.

Rollback anchor: main V75 `64619fbfe3967868a88085c4c4084ddcce4759ac`.

Rollback: discard/revert the V76 candidate and restore the Android packaging workflow to the V75 tree. No provider secrets are introduced by V76.
