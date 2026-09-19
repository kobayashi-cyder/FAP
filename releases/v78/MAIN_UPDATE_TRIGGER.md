# FAP v78 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `f0120980fbac875dfc7206b000c55c601598c41d`
- Commit date: `2026-09-19T21:33:54+09:00`
- Commit message: Add bounded retry delay hook
- Latest completed release detected on main: `v77`
- Prepared work branch: `listener/v78`

## Changes since the previous processed main state

```
M	candidates/goal_completion_loop/fap_goal_loop/resilient_capability.py
M	candidates/goal_completion_loop/tests/test_resilient_capability.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v78` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v78/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
