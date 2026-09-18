# FAP v78 preparation context

- Inherited branch: `main`
- Inherited main SHA: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`
- Highest completed release on inherited main: `v77`
- Rollback anchor: `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (discard/revert v78-only work)

## Changed surfaces
The newly completed v77 state records an independently verified KEEP decision for the bounded HTTPS image-provider adapter. V77 has deterministic injected-transport tests and latency measurement, while real provider output remains explicitly unverified.

## Compatibility constraints
Preserve V77's bounded HTTPS boundary, environment-only bearer credentials, response validation, deterministic injected-transport behavior, and all V66–V75 regressions. Do not convert the V77 KEEP decision into a claim that real image generation works without real-backend evidence.

## Likely implementation targets
1. Real-backend/provider compatibility probe behind the existing adapter boundary, with secrets supplied only through environment/runtime configuration.
2. Evidence capture that records provider/backend identity, request/response schema compatibility, bounded payload metadata, latency and failure mode without storing credentials.
3. Android-facing network integration contract only after backend compatibility is demonstrated; keep Android packaging independent from provider secrets.
4. Bounded retry/timeout behavior only if supported by measurements and tests; avoid unbounded buffering or streaming state.

## Regression hazards
Credential leakage; provider-specific schema coupling; accepting malformed/oversized responses; unbounded RAM/storage; nondeterministic tests that depend on a live provider; falsely promoting mocked transport success to real-generation success; Android cleartext/network-security or lifecycle regressions.

## Android / packaging implications
No provider secret may be embedded in APK/AAB/resources. Any Android integration must use HTTPS, bounded response handling, explicit timeout/error states and lifecycle-safe cancellation. Packaging/provenance should identify the FAP/main source SHA and adapter contract independently of runtime credentials/provider output.

## Required verification
Run compile checks and v78 focused tests, then V77 focused tests, V75–V69 focused regressions and V66–V68 core regressions on Python 3.11/3.12. If a real backend is exercised, record sanitized evidence for schema compatibility, successful output validation, latency, payload bounds and failure handling. Android claims require separate device/emulator integration evidence.

## Likely next planned experiment
Exercise exactly one real image backend through the existing V77 adapter with runtime-only credentials; validate one bounded successful response plus representative authentication/schema/timeout failures, record sanitized evidence, and leave production/Android readiness DEFER unless those surfaces are independently verified.
