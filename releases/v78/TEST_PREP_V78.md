# V78 TEST PREP — real image provider evidence gate

Base/rollback anchor: main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). Verify V78 independently; do not modify main or media sibling lanes.

## Deterministic gate
- Unit-test provider translation, evidence schema/redaction, bounded transport/decoder handoff with fixed fixtures and stable hashes.
- Malformed request/response: invalid schema/JSON/base64, missing fields, illegal dimensions, credential-in-URL, non-HTTPS.
- Missing provider/credential must fail closed without generation claim.
- Inject timeout, DNS/transport error, HTTP non-2xx, provider error, wrong/unsupported MIME, zero-byte/empty artifact, truncated artifact, decoder rejection and hash mismatch.
- Enforce configured request and response byte ceilings plus width/height limits at exact boundary and boundary+1; oversized data must be rejected before retention/export.
- Fixtures must be local/reproducible, small, decodable where positive, and contain no live credential or user prompt.

## Real-backend evidence gate
No real-generation claim until the concrete adapter is independently exercised against its actual backend, outside mocked/injected transport. Evidence must identify adapter/provider, outcome, MIME, dimensions, byte count/hash and measured wall latency; capture peak RSS delta and retained-storage bytes where supported, otherwise mark unavailable. Evidence must not contain credentials, prompt text or raw image by default.

## Privacy/resource assertions
Prompt/result logging and telemetry off by default; retries off; temporary response bytes released after validation unless caller explicitly exports. Assert evidence serialization cannot retain secret, prompt or raw payload. Record latency/RAM/storage from the independent run without estimates.

## Regression gate
Run V77 focused adapter/evidence tests, current V69/V70 regressions, and V66-V68 core regression suites applicable to the candidate. No skip/xfail/deletion may mask an inherited failure. Compile/import checks and resource probe must pass in the supported CI matrix.

## Rollback / disable
Rollback to `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`, or disable/remove the provider adapter while preserving the provider-neutral boundary, on validation bypass, secret/prompt/raw-output leakage, unbounded allocation, unexplained regression, or backend behavior that cannot be bounded/reproduced. If backend/credential/network or independent exercise is unavailable, DEFER real generation and allow only truthful provider-neutral probe/evidence plumbing.

Android audio permission, microphone/audio-focus/output lifecycle and voice-mode tests are not applicable to this image-only candidate. Half-duplex remains the voice baseline; full-duplex, barge-in, echo cancellation, wake-word and streaming require separate candidates/tests.