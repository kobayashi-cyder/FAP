# V78 TEST PREP — image evidence gate

Base/rollback: `main@de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (integrated V77). Do not reprocess V69/V70; run their regressions plus V66–V68 core regressions.

## Deterministic gate
- Unit-test request validation, budgets, cancellation, metadata and provider-neutral error mapping with fixed fixtures and clocks.
- Malformed/oversize request; missing provider/credential; timeout/cancel/provider error; wrong MIME/signature; empty/truncated artifact; unsupported format; dimensions/response bytes over limit all fail closed.
- Reproducible fixtures include valid tiny image, MIME mismatch, truncated bytes, empty bytes, oversized metadata/payload; record fixture hashes.
- Independent verifier must decode returned bytes and validate MIME/signature/dimensions without trusting adapter success flags.

## Real-backend evidence
No `real generation` claim unless one concrete image adapter is independently invoked against its real backend and the resulting artifact is independently decoded. Record redacted backend identity, request/result metadata, content hash, MIME, dimensions, byte count, round-trip/decode latency and peak RSS. Never commit credentials or prompt/image payloads by default.

## Privacy/resources
Assert `retained=false` default, ephemeral prompt/artifact handling, no secret/payload logging, and explicit opt-in before persistence. Measure peak RSS delta, p50/max provider latency over a bounded reproducible sample, decode latency, temporary/persisted bytes and requested/actual dimensions; report measured values rather than invented thresholds.

## Regression/promotion
Run V77 image HTTP tests, current V69/V70 regressions and V66–V68 core suites on the candidate. KEEP only if all deterministic/negative/regression gates pass and real-backend evidence requirements pass; otherwise DEFER the generation claim. Roll back/disable the adapter on validation bypass, unbounded resource use, cancellation failure, unsafe retention, provider-contract leakage into core, or repeated error-semantic violations. V78 remains image-only; no STT/TTS/video/voice claims.
