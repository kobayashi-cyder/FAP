# V81 TEST PREP — bounded chat reliability

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify V81 independently of V78-V80 and media sibling lanes; do not modify main.

## Deterministic gate
- Unit-test request/context construction, provider-neutral response/error envelopes, deterministic truncation, cancellation/timeout and capability reporting with fixed fixtures.
- Reject empty/oversized input, malformed role/message structure, invalid UTF-8/response schema, context at limit and limit+1, empty/oversized response and duplicate completion.
- Missing provider must fail closed without silent provider substitution or capability inflation.
- Inject timeout, cancellation races, transport/non-2xx/provider errors and malformed responses; retries remain off by default.
- Exercise request/response byte ceilings and context budget boundaries reproducibly; release bounded context buffers after completion unless explicitly caller-owned.

## Provider evidence
Provider-neutral reliability may KEEP without a live provider claim. Any concrete chat-provider claim requires independent non-mocked backend exercise identifying adapter/provider, outcome, bounded request/response counts and measured wall latency; capture peak RSS delta and retained-storage bytes where feasible. Evidence excludes message text, credentials and raw provider payloads.

## Privacy/resources
Conversation/provider-payload logging and telemetry are off by default. Assert redaction of secret-like metadata and zero unintended retained message/provider bytes after success, error, timeout and cancellation. Repeated-call tests detect RSS/storage/task growth; unsupported metrics are `unavailable`, never estimated.

## Regression gate
Run current V69/V70 regressions and applicable V66-V68 core suites; run V77 shared adapter/evidence tests only where shared boundaries are touched. No skip/xfail/deletion may hide inherited failures. Compile/import and resource probes pass in the supported matrix.

## Rollback/disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable the concrete chat adapter while retaining provider-neutral contracts, on privacy leak, nondeterministic truncation, unbounded context/RAM growth, cancellation leak, misleading capability reporting, backend incompatibility or unexplained regression. DEFER provider-specific claims when independent backend evidence is unavailable.

No microphone/audio-focus/output behavior belongs here. Half-duplex voice baseline is unchanged; full-duplex, barge-in, echo cancellation, wake-word and streaming require separate tests.