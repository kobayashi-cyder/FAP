# FAP v78 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `be71d02ec8635ea624f1a3577429650d0b84b195`
- Commit date: `2026-09-19T12:52:25+09:00`
- Commit message: Add fail-closed resilient capability retry policy
- Latest completed release detected on main: `v77`
- Prepared work branch: `listener/v78`

## Changes since the previous processed main state

```
A	candidates/goal_completion_loop/fap_goal_loop/resilient_capability.py
A	candidates/goal_completion_loop/tests/test_resilient_capability.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v78` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v78/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
