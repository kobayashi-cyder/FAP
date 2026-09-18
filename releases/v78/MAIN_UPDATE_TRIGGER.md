# FAP v78 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `517486b63f92789856451e07f214b726274e4731`
- Commit date: `2026-09-19T08:59:44+09:00`
- Commit message: Cross-pollinate FCA sparse capability gating into goal runtime
- Latest completed release detected on main: `v77`
- Prepared work branch: `listener/v78`

## Changes since the previous processed main state

```
M	.github/workflows/goal-completion-loop-verify.yml
A	candidates/goal_completion_loop/FCA_CROSS_POLLINATION.md
A	candidates/goal_completion_loop/exchange/fca_sparse_control.json
M	candidates/goal_completion_loop/fap_goal_loop/__init__.py
A	candidates/goal_completion_loop/fap_goal_loop/exchange.py
M	candidates/goal_completion_loop/fap_goal_loop/runtime.py
A	candidates/goal_completion_loop/fap_goal_loop/sparse_gate.py
A	candidates/goal_completion_loop/tests/test_fca_cross_pollination.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v78` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v78/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
