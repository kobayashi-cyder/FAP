# Integration prep — V70 media provider adapters

Preferred V70 candidate due explicit current user priority.

Main base/rollback anchor:
`e338d9bb70afd7d46fd2465feaedc3d133630e6a` (V69).

Expected main delta is additive:
- `releases/v70/media_adapters/fap_provider_adapters/**`
- focused tests/fixture
- V70 media-adapter prep/test/decision docs
- dedicated CI workflow

Do not merge `skill/v70-deterministic-replay` wholesale. Its older plan may be resumed as a
later version after current interaction work is stable.

No Android package/applicationId, persistence schema, V69 interaction API, or V68 code
factory mutation is allowed in this unit.
