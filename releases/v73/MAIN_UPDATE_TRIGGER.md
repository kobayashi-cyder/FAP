# FAP v73 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `69f04a36efb33287542d58cff88ff27440db334d`
- Commit date: `2026-09-18T12:47:03+09:00`
- Commit message: V72: Half-duplex audio session lifecycle
- Latest completed release detected on main: `v72`
- Prepared work branch: `listener/v73`

## Changes since the previous processed main state

```
A	.github/workflows/v72-audio-lifecycle-verify.yml
A	releases/v72/DECISION_AUDIO_LIFECYCLE.md
A	releases/v72/PREP_V72_AUDIO_LIFECYCLE.md
A	releases/v72/TEST_PREP_V72_AUDIO_LIFECYCLE.md
A	releases/v72/audio_lifecycle/fap_audio_lifecycle/__init__.py
A	releases/v72/audio_lifecycle/fap_audio_lifecycle/session.py
A	releases/v72/audio_lifecycle/tests/test_audio_session.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v73` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v73/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
