# V69 Skill Lane — Android Artifact Provenance

Base: main `d6329968a579fa0d20dbdb115a6f7a060d13a68e`.

## Goal
Let Android/runtime state identify the exact source release and evidence that produced an installed artifact without changing legacy schema-1/schema-2 writers.

## Prototype
- `android_artifact_provenance.py`
- additive schema 3 writer
- source commit, release, release-manifest SHA-256, verification SHA-256
- atomic temp-file + fsync + replace write
- no changes to existing `AndroidStateSync` or `AndroidV65StateSync`

## Verified locally
- 2/2 unit tests PASS.

## Integration preparation
Do not replace schema 2. The future coordinator should emit schema 3 in parallel until consumers prove compatibility.

Required next work:
1. bind actual APK/AAB digest and package/versionCode;
2. derive verification digest from reproducible EvidenceManifest;
3. add read/verify side on Android;
4. test schema 1/2 output remains unchanged;
5. test interrupted write and stale artifact metadata.

Decision gate: KEEP only if an installed artifact can be traced to source/evidence with no compatibility regression.
