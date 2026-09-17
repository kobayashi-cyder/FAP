# FAP v62 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `b0016605ff2739e67777a99e47cdccb46363dd6a`
- Commit date: `2026-09-18T06:39:44+09:00`
- Commit message: Add main update listener for next release preparation
- Latest completed release detected on main: `v61`
- Prepared work branch: `listener/v62`

## Changes since the previous processed main state

```
A	.github/workflows/main-update-listener.yml
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v62` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v62/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
