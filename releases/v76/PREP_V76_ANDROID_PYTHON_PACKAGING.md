# V76 candidate — Android interaction-package packaging

Status: implementation candidate, non-main.
Base/rollback anchor: main V75 `64619fbfe3967868a88085c4c4084ddcce4759ac`.

## Problem found
The Android build workflow currently copies the legacy `fap_core.py` and only a latest-release
`fap_autonomy` sidecar. Main-integrated V69-V75 packages therefore are not guaranteed to be
inside the APK.

## Scope
- declarative manifest for V69-V75 Python interaction packages;
- deterministic stdlib-only package synchronizer;
- reject missing sources, duplicate destinations, path escapes and symlinks;
- replace stale destination package trees;
- content tree SHA-256/file count/byte count per package;
- deterministic interaction-package report embedded in APK Python assets;
- APK_INFO records report SHA-256;
- build workflow compiles the complete packaged Python tree.

## Non-claims
Packaging code into the APK does not mean Android UI or microphone/speaker code invokes every
package. V76 proves packaging/build availability only. Runtime/UI wiring remains a later
version and must be independently verified.

## Promotion
Require unit tests, a sync against the real repository manifest, compileall of the synced tree,
V75-V69 regressions, V66-V68 core regressions, and independent CI on Python 3.11/3.12.
After main merge, the Android APK workflow itself must succeed before claiming APK packaging.
