# FAP v74 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `86b4c04f90f3c6495ef3190d361bb33a7068acf4`
- Commit date: `2026-09-18T12:49:26+09:00`
- Commit message: V73: Provider capability probe and gating
- Latest completed release detected on main: `v73`
- Prepared work branch: `listener/v74`

## Changes since the previous processed main state

```
A	.github/workflows/v73-provider-probe-verify.yml
A	releases/v73/DECISION_PROVIDER_PROBE.md
A	releases/v73/PREP_V73_PROVIDER_PROBE.md
A	releases/v73/TEST_PREP_V73_PROVIDER_PROBE.md
A	releases/v73/provider_probe/fap_provider_probe/__init__.py
A	releases/v73/provider_probe/fap_provider_probe/probe.py
A	releases/v73/provider_probe/tests/fixtures/probe_provider.py
A	releases/v73/provider_probe/tests/test_provider_probe.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v74` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v74/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
