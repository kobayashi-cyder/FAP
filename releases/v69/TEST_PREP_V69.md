# TEST PREP V69 — Evidence-bounded Android provenance observability

Status: PREPARED WITH ACTIVE BLOCKER, non-binding. Verification base: main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

## Scope
Verify only the additive V69 Android artifact provenance record/verifier described by PREP_V69. Do not treat the older `skill/v69-android-provenance` branch as evidence until individual files are reconciled with current V68. Do not change Android applicationId/package behavior or existing schema 1/2 writers.

## Active independent-CI blocker
Exact candidate HEAD `8108f66457e93b8462aaf84b275d7c13abb0fbb8` has independent GitHub Actions evidence: Python 3.11 completed compile, focused V69 tests, current V68 cumulative regression, and resource probe successfully; Python 3.12 completed compile and focused V69 tests successfully but failed the current V68 cumulative regression, so the resource probe was skipped. V69 remains MODIFY and is not eligible for KEEP.

Before changing V69 implementation, reproduce the failing V68 cumulative command on (a) current main V68 and (b) the exact V69 candidate under the same Python 3.12 runner/tool versions. Capture the failing test names, traceback/output, exit status, Python version, and dependency/tool versions. Classify the failure as baseline/Python-3.12 incompatibility versus V69-induced regression. Do not weaken, skip, xfail, or remove the cumulative test to obtain green CI. If main itself fails identically, record that independently and keep V69 blocked until the baseline policy is explicitly resolved; if only V69 fails, repair V69 and rerun the full matrix on one new exact HEAD.

## Deterministic focused tests
- identical artifact bytes + identical metadata serialize identically across repeated runs/restart;
- SHA-256 is recomputed from artifact bytes, not trusted from caller input;
- manifest and verification-summary digests are recomputed when supplied;
- immutable record round-trip preserves package, versionCode/versionName, source SHA, release id and digests;
- optional manifest absence is accepted only when the record explicitly marks it absent.

## Fail-closed / malformed-input matrix
Reject: one-byte artifact mutation; truncated/missing artifact; malformed/wrong artifact hash; wrong package/versionCode/versionName; malformed/wrong source commit SHA; manifest digest mismatch; verification-summary digest mismatch; malformed serialization; duplicate/conflicting fields; path substitution; symlink substitution where supported. Adapter exceptions must become explicit verification failures, not implicit success. Add an explicit symlink/path-substitution test before KEEP; current implementation evidence does not close this item.

## Android adapter evidence
Keep package/build metadata extraction outside the pure verifier. Unit tests use reproducible tiny binary fixtures. Before any claim of real APK/AAB integration, independently exercise a concrete Android/build-tool adapter against an actual artifact, recompute the artifact hash, and verify package/version metadata. Synthetic fixtures must remain labelled synthetic. No signing, Play Integrity, or remote-attestation claim is permitted from this evidence.

## Regression / compatibility
Run focused V69 tests plus warnings-as-errors compile/static checks and the current V68 cumulative regression suite from the same candidate HEAD on every supported CI Python version. Verify existing Android schema 1/2 outputs byte-for-byte or semantically unchanged where deterministic. Verify no new runtime permission and no applicationId/package-name change. Any V68 regression blocks promotion until classified and resolved without weakening tests.

## Reproducibility and resource evidence
Fixtures must be committed/generated deterministically with documented SHA-256. Measure serialized record size, hashing latency, and peak memory for a tiny fixture and a representative larger fixture where feasible. Prefer streaming hashing; flag whole-artifact buffering as MODIFY if peak memory scales with artifact size. Record OS/Python/tool versions for reproducible measurements. Resource evidence must run successfully on all required matrix legs after regression repair; a skipped probe is not evidence.

## Privacy / retention assertions
Provenance output may contain build metadata and cryptographic digests only. Tests must assert absence of user content, microphone/audio data, device identifiers, tokens/secrets, absolute private filesystem paths, and telemetry payload bodies. No broad Android storage permission may be introduced.

## Independent evidence rule
A self-authored verification summary digest proves only integrity of that summary, not that tests ran. Promotion requires independently rerunnable commands/results from the exact candidate HEAD. Do not mark PASS from documentation alone.

## Rollback / disable
Rollback anchor is current V68 main `929c419b3fcff55720e159b8f7f7f1d602dec305`. V69 must be removable/disableable without migration of V68 state. Failure to preserve schema 1/2 compatibility, package behavior, or clean removal is a promotion blocker.

## Decision gates
KEEP only if focused tests, malformed-input matrix including symlink/path substitution, all supported-version current-main cumulative regressions, compile/static checks, deterministic evidence, resource probes, privacy assertions and rollback checks pass on the same candidate HEAD. MODIFY for bounded implementation/test defects with no architectural break. DEFER real Android integration claims when no concrete APK/AAB adapter is independently exercised. REPLACE if current repository already contains equivalent byte-bound provenance with stronger independent tests. KILL if the slice requires invasive schema/package changes or cannot fail closed.

Do not advance V70 verification as a promotion-path substitute while V69 has this unresolved contiguous blocker.

Highest-risk untested assumptions: the Python 3.12 V68 cumulative regression failure has not yet been classified; symlink/path substitution remains unverified; and real APK/AAB package extraction remains unproven until a concrete adapter is independently exercised.
