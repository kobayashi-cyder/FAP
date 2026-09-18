# V78 PREP — real image provider evidence gate

Base and rollback anchor: actual main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` (V77 KEEP). This candidate does not modify main and does not assume V69/V70 work remains pending.

## Goal
Small independent candidate that turns V77's bounded HTTP adapter into a truthful capability gate. Prefer one concrete image provider/renderer adapter only if a real backend can be exercised independently. Otherwise keep the existing provider-neutral boundary and add only evidence capture/probe plumbing. No image-generation claim without independently verified decodable output.

## Expected files/interfaces
- `releases/v78/image_provider/adapter.py`: provider-specific request/response translation behind the V77 bounded transport, only if real backend evidence is obtainable.
- `releases/v78/image_provider/evidence.py`: redacted evidence record containing provider/adapter identity, dimensions/MIME, byte count/hash, latency and outcome; never prompt text, credentials or raw image by default.
- `releases/v78/test_image_provider.py`: deterministic negative/boundary tests plus evidence-schema tests.
- `releases/v78/DECISION_IMAGE_PROVIDER.md`: KEEP/DEFER/REPLACE decision and independent-run reference.

Boundary: FAP core -> provider-neutral image request -> provider adapter -> bounded HTTPS transport -> provider -> validated encoded image -> decoder/evidence gate. Provider schema and credentials must not leak into core interfaces.

## Negative tests
Missing credential; credential embedded in URL; non-HTTPS endpoint; timeout; DNS/transport failure; HTTP non-2xx; malformed JSON/base64; unsupported MIME; zero-byte/truncated/oversized payload; dimensions outside configured bounds; decoder rejection; response/hash mismatch; evidence accidentally containing secret/prompt/raw payload. All fail closed and must not be reported as generated images.

## Android implications
No Android integration is required for V78. A later Android consumer must use platform network policy, bounded decode dimensions, background execution rather than UI-thread network work, and explicit storage/export action. No microphone/audio permission belongs in this image candidate.

## Privacy/resource defaults
Credentials environment/runtime only; prompt/result logging off; telemetry off; retries off; raw output not retained by evidence recorder; temporary bytes released after validation unless caller explicitly exports. Measure wall latency, peak process RSS delta where supported, encoded bytes and retained storage bytes. Record unavailable metrics as unavailable, never estimated. Set implementation bounds before promotion (timeout, response-byte ceiling, width/height ceiling).

## Promotion evidence
KEEP generation capability only with: (1) concrete adapter code, (2) real backend invocation outside mocked transport, (3) independently run evidence showing successful HTTP/provider response and decoder acceptance, (4) output MIME/dimensions/bytes/hash and measured latency, RAM/storage metrics or explicit unavailable markers, (5) focused negative tests and existing regression suite green, and (6) no secret/prompt/raw-output leakage in evidence. Mock/injected-transport success alone is insufficient.

## DEFER / REPLACE
DEFER real generation if credentials/backend/network or independent verification is unavailable; in that case V78 may land only provider-neutral evidence/probe plumbing and must say generation is unverified. REPLACE a provider adapter if its schema/auth/terms make bounded validation impossible, it requires secret persistence, or another adapter provides stronger reproducible evidence with a smaller surface. Do not merge media sibling branches automatically.

Full-duplex, barge-in, echo cancellation, wake-word and streaming remain separate later capabilities.
