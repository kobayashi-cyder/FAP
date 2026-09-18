# V83 TEST PREP — bounded practical chat-turn capability

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify V83 independently of V78-V82 and every media sibling lane; do not modify main.

## Deterministic gate
- Unit-test request/context construction, deterministic truncation, neutral response/error envelopes, deadlines, cancellation and stale/duplicate completion handling with fixed local fixtures.
- Reject malformed role/order/schema, invalid UTF-8, empty input, oversized input/context/output and response conversion failures. Exercise request/context/response byte limits at exact boundary and boundary+1.
- Missing/disabled provider fails closed with explicit unavailable result; no silent provider substitution or capability inflation.
- Inject provider timeout/error/exception, transport/non-2xx failures, malformed/empty response and cancellation before/during/after completion. Retries remain off by default.
- Fixtures are reproducible, bounded and credential/user-content free.

## Concrete-adapter evidence gate
Provider-neutral chat reliability may be verified without a live model claim. Any real chat-provider claim requires independent exercise of the exact concrete adapter against its actual non-mocked backend. Evidence records adapter/provider identity, outcome, bounded request/context/response counts and measured wall latency; capture peak RSS delta and retained-storage bytes where feasible, otherwise `unavailable`. Evidence excludes credentials, message text and raw provider payloads.

Image/STT/TTS are out of scope. If introduced, require their own isolated adapter verification including malformed input, missing provider, timeout/error, wrong MIME where applicable, empty artifact/transcript, size bounds and independent real-backend exercise before generation/transcription/synthesis claims.

## Privacy/resources
Prompt, response, conversation and provider-payload logging/telemetry are off by default. Assert bounded active-call/context refs are released on success/error/timeout/cancel unless explicitly caller-owned. Run 100-cycle success/failure/cancel checks for RSS/storage/handle/task growth; record latency, peak RAM, byte high-water marks and retained storage where feasible.

## Regression gate
Run current V69/V70 regressions plus applicable V66-V68 core suites; run V77/shared adapter-evidence regressions only where shared boundaries are touched. No skip/xfail/deletion may hide inherited failures. Compile/import and resource probes must pass in the supported matrix.

## Rollback/disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable the concrete chat adapter while preserving neutral contracts, on privacy/bounds bypass, nondeterministic truncation, stale callback mutation, cancellation/resource leak, misleading capability reporting, backend incompatibility or unexplained regression. DEFER provider-specific claims when independent backend evidence is unavailable.

No microphone/audio-focus/output behavior belongs in V83. Half-duplex voice baseline is unchanged; full-duplex, barge-in, echo cancellation, wake-word and streaming require separate tests.