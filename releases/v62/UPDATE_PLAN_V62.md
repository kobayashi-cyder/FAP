# FAP v62 update plan

Source main commit: `b0016605ff2739e67777a99e47cdccb46363dd6a`

## Change assessed

The only main change since `447c85cefdfa946ed67db671d93737013cd05665` is the addition of `.github/workflows/main-update-listener.yml`.

## Impact assessment

- FAP runtime behavior: no runtime code changed.
- Tests: no existing runtime tests require modification for this commit.
- Packaging: the Android APK build workflow is unchanged; the new listener runs independently on pushes to `main`.
- Android integration: no Android source or packaging inputs changed.
- Release workflow: `main` pushes now prepare/refresh `listener/v62` and record the triggering main SHA and changed-file set.

## v62 work direction

1. Treat the listener infrastructure as release tooling, not as a behavioral FAP release by itself.
2. On the next substantive `main` update, inspect runtime, tests, packaging, and Android impact before modifying v62 implementation.
3. Keep implementation and validation changes on `listener/v62` until coherent and verified.
4. Preserve unrelated work and avoid direct writes to `main`.

## Validation for this iteration

Static inspection confirms the listener is scoped to `push` on `main`, writes to a non-main `listener/vNN` branch, derives the next release from `releases/vNN`, and records source metadata. No FAP runtime or Android build code is modified by the triggering commit.
