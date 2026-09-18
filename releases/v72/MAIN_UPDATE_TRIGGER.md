# FAP v72 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `5eaf8a7aa9ce30972ede0c025ee5e118132669b8`
- Commit date: `2026-09-18T12:45:33+09:00`
- Commit message: V71: Interaction runtime capability router
- Latest completed release detected on main: `v71`
- Prepared work branch: `listener/v72`

## Changes since the previous processed main state

```
A	.github/workflows/v71-interaction-runtime-verify.yml
A	releases/v71/DECISION_INTERACTION_RUNTIME.md
A	releases/v71/PREP_V71_INTERACTION_RUNTIME.md
A	releases/v71/TEST_PREP_V71_INTERACTION_RUNTIME.md
A	releases/v71/runtime/fap_runtime/__init__.py
A	releases/v71/runtime/fap_runtime/interaction_runtime.py
A	releases/v71/runtime/tests/test_interaction_runtime.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v72` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v72/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
