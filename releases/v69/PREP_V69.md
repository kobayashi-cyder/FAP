# PREP V69 — Evidence-bounded Android provenance observability

Status: PREPARED, non-binding. Base main: `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

## Re-plan from current repository

Current main V68 is no longer the evidence-retention plan assumed by the older `skill/v69-android-provenance` experiment. V68 now implements TaskPlan AST repair + candidate-race code factory. Therefore V69 must be a small additive observability slice and must not import or merge the stale V69 branch wholesale.

## Smallest coherent experiment

Add an Android artifact provenance record/verifier that binds an artifact to:
- package name and versionCode/versionName;
- artifact SHA-256 computed from actual APK/AAB bytes;
- exact source/main commit SHA;
- release/version identifier and release-manifest digest when present;
- verification summary digest, without treating a self-authored summary as independent evidence.

Expected new files should stay under `releases/v69/` (for example `fap_autonomy/android_provenance.py`, focused tests, demo/report). Do not mutate existing Android schema 1/2 writers. Add schema 3 only if a concrete consumer requires it and compatibility tests justify it.

## Interfaces / boundaries

`build_provenance(artifact_path, package_metadata, source_sha, release_manifest, verification_summary) -> immutable record`

`verify_provenance(record, artifact_path, expected_package=None) -> result`

The verifier must recompute artifact bytes SHA-256 and any supplied manifest/summary digest. It must fail closed on malformed hashes, missing artifact, package/version mismatch, source-SHA mismatch, truncation, or changed bytes. Provenance is traceability, not signing, remote attestation, Play Integrity, or proof that tests actually ran.

## Required negative tests

- one-byte APK/AAB mutation;
- wrong package/versionCode/versionName;
- wrong or malformed source SHA;
- missing/truncated artifact;
- manifest digest mismatch and absent optional manifest;
- verification-summary digest mismatch;
- path/symlink substitution where applicable;
- deterministic serialization and cross-restart verification.

Use tiny reproducible binary fixtures; no real signing key or production APK is required for unit tests. A real Android artifact is required before claiming package/build integration.

## Android implications

No new runtime permission should be required for offline verification of app-owned artifact metadata. Do not request broad storage permission. If package metadata is read from Android APIs/build tooling, isolate that adapter from the pure verifier and test adapter failure separately. Do not change applicationId/package behavior in this version.

## Privacy / resources

Record only build/provenance metadata and cryptographic digests; no user content, microphone/audio, device identifiers, tokens, filesystem secrets, or telemetry payload bodies. Measure record size, hashing latency and peak memory on at least a small and representative larger fixture where feasible. Streaming hashing is preferred over reading entire artifacts into RAM.

## Promotion evidence

Require focused deterministic tests, malformed-input tests, compile/static checks, current V68 cumulative regression, and independently rerunnable artifact-byte verification. If a real APK/AAB is available, verify its bytes and package metadata through the concrete adapter. Clearly label synthetic fixtures as synthetic.

## Rollback

V69 must be additive. Rollback is removal/disable of the V69 provenance writer/verifier with no migration of V68 state. Existing Android schema 1/2 and V68 code-factory behavior must remain unchanged.

## DEFER / REPLACE conditions

DEFER schema-3 export until a concrete consumer and compatibility evidence exist. DEFER signing/Play Integrity/remote attestation to a separate version. REPLACE this plan if current Android packaging already exposes an equivalent byte-bound provenance record with independent tests; then V69 should become a focused compatibility/verification experiment rather than duplicate it.

## Relationship to existing non-main experiment

`skill/v69-android-provenance` is advisory only and predates current V68 main. Reuse individual files only after diffing/rebasing their assumptions against current main; do not merge the branch wholesale.
