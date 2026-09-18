# FAP v78 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `eb75aad4be2d35cb376fb6750f772c00727934e4`
- Commit date: `2026-09-19T07:52:05+09:00`
- Commit message: Wire conversation instructions into autonomous goal loop
- Latest completed release detected on main: `v77`
- Prepared work branch: `listener/v78`

## Changes since the previous processed main state

```
M	.github/workflows/goal-completion-loop-verify.yml
M	candidates/goal_completion_loop/README.md
A	candidates/goal_completion_loop/RUNTIME_WIRING.md
M	candidates/goal_completion_loop/fap_goal_loop/__init__.py
M	candidates/goal_completion_loop/fap_goal_loop/goal_loop.py
A	candidates/goal_completion_loop/fap_goal_loop/runtime.py
A	candidates/goal_completion_loop/tests/test_runtime.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v78` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v78/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
