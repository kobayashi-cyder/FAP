# V69 implementation report — Android artifact provenance

Decision: **MODIFY** (not promoted; independent verification incomplete).

Base / rollback anchor: main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68). This slice is additive under `releases/v69/`; rollback is branch deletion/non-promotion and requires no V68 state migration.

## Implemented
- immutable deterministic provenance record;
- streaming SHA-256 over actual artifact bytes;
- package/version/source/release binding;
- optional manifest and verification-summary digests with explicit presence semantics;
- fail-closed verifier and strict mapping parser;
- focused mutation, truncation/missing-file, metadata/source mismatch, malformed mapping, optional-evidence and privacy tests;
- branch-only CI matrix for Python 3.11/3.12, V67/V68 cumulative regression and a 16 MiB peak-memory probe.

## Evidence status
The branch source/tests/CI definition are committed, but no independent GitHub Actions run was visible immediately after the CI workflow commit. Therefore this run does **not** claim PASS or KEEP. Synthetic fixtures are not evidence of real APK/AAB package extraction.

## Remaining verification / limitations
1. Obtain an independent CI result on this exact branch HEAD; all focused tests, warnings-as-errors compile, V67/V68 regression and resource probe must pass.
2. Real Android integration remains DEFER until a concrete APK/AAB metadata adapter is independently exercised against an actual artifact. No signing, Play Integrity or remote-attestation claim is made.
3. Symlink/path-substitution behavior needs an explicit test before KEEP; current hashing follows the filesystem path.
4. Existing Android schema 1/2 and applicationId/package behavior must be checked unchanged before promotion.

## Next action
Continue V69 rather than starting V70 until the independent CI/evidence gate is satisfied. If CI exposes a bounded defect, repair on this branch and rerun without weakening tests. If stable Android package metadata cannot be obtained without invasive schema/package changes, DEFER or REPLACE the adapter portion while retaining the pure byte-bound verifier only if independently useful.
