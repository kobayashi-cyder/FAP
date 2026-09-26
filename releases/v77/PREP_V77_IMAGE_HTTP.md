# V77 candidate — concrete image HTTP adapter boundary

Base/rollback anchor: V76 candidate `736029321620e418bb8c835291fbbcae47897645` (main remains V75).

Goal: smallest provider-specific network boundary needed to exercise a real image backend later without committing secrets.

Scope: credential-free HTTPS endpoint validation; bearer credential sourced only from a named environment variable; bounded prompt/dimensions/timeout/response bytes; JSON/base64 image response validation; fail-closed errors; latency measurement; injectable transport for deterministic tests.

Privacy defaults: no secret persistence, no prompt/result logging, no retry, no telemetry. Provider endpoint must not contain credentials.

Non-claims: no real provider/backend is available to this run, so V77 does NOT claim real image generation or output quality. Streaming is out of scope.

Prepared verification: focused V77 tests, compileall, V75-V69 focused regressions and V66-V68 core regressions on Python 3.11/3.12. Real-provider verification remains separately required before generation capability can be claimed.
