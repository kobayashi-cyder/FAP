# FAP v71 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `c4a3f5d3c7a0590c7506f807ac4881b94524a5a3`
- Commit date: `2026-09-18T12:36:27+09:00`
- Commit message: V70: Trusted local media provider adapters
- Latest completed release detected on main: `v70`
- Prepared work branch: `listener/v71`

## Changes since the previous processed main state

```
A	.github/workflows/v70-media-provider-verify.yml
A	releases/v70/DECISION_MEDIA_ADAPTERS.md
A	releases/v70/INTEGRATION_PREP_MEDIA_ADAPTERS.md
A	releases/v70/PREP_V70_MEDIA_ADAPTERS.md
A	releases/v70/TEST_PREP_V70_MEDIA_ADAPTERS.md
A	releases/v70/media_adapters/fap_provider_adapters/__init__.py
A	releases/v70/media_adapters/fap_provider_adapters/command_json.py
A	releases/v70/media_adapters/fap_provider_adapters/providers.py
A	releases/v70/media_adapters/tests/fixtures/provider_fixture.py
A	releases/v70/media_adapters/tests/test_provider_adapters.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v71` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v71/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
