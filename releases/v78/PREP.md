# V78 PREP — Image renderer/provider boundary

Status: PREP ONLY. Base is the actual `main` commit `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` observed at preparation time. V69/V70 are treated as already integrated and are not reprepared. This branch is an independent media-skill lane; do not merge sibling PREP branches automatically.

## Scope
Small provider-neutral image-generation boundary. No claim of real image generation is made in V78 because this PREP contains no independently executed real renderer/backend evidence. Real generation is DEFERRED until a concrete backend is wired and its output is independently evidenced.

## Expected files / interfaces
- `src/fap/media/image/ImageRequest.*`: prompt, width, height, seed/options with bounded sizes.
- `src/fap/media/image/ImageResult.*`: success/error, MIME type, dimensions, byte/file reference, provider metadata without secrets.
- `src/fap/media/image/ImageProvider.*`: `generate(request) -> result` contract.
- `src/fap/media/image/ImageRenderer.*`: validates/decodes provider result and exposes a renderer-neutral artifact.
- `src/fap/media/image/providers/DisabledImageProvider.*`: fail-closed default.
- `tests/media/image_provider_contract.*`
- `tests/media/image_negative.*`
- `bench/media/image_boundary_bench.*`

Provider/renderer boundary: provider owns backend invocation and backend-specific response mapping; renderer owns validation/decoding/display-ready artifact construction. Core/chat code depends only on `ImageProvider`/`ImageResult`, never a provider SDK.

## Negative tests
Reject empty/oversized prompts, unsupported dimensions/MIME, malformed/truncated payloads, path traversal, provider timeout, cancellation, backend unavailable, oversized output, decode failure, and secret-bearing metadata. Disabled provider must return a typed unavailable result and must never fabricate an image.

## Privacy / retention defaults
No prompt or image persistence by default. No API keys/tokens in logs, results, telemetry, fixtures, or provider metadata. Temporary artifacts are process/session scoped and deleted on cancellation/failure/normal cleanup unless an explicit caller-owned save policy is supplied. Network use is opt-in through provider configuration.

## Required metrics before promotion
Record peak RSS delta (MiB), request-to-result boundary overhead (p50/p95 ms, excluding backend separately from end-to-end), encoded output bytes, decoded image bytes, temporary-storage peak, cancellation cleanup time, and leak count after repeated runs. Test at minimum one small and one maximum-supported image.

## Promotion evidence
Promotion requires: contract + negative tests green; bounded-resource benchmark report; repeated cleanup test; and, for any claim of real generation, independent evidence from a concrete renderer/provider consisting of invocation record, non-fixture generated artifact/hash, dimensions/MIME validation, elapsed time, peak RSS/storage, and backend identity/version. Without that evidence V78 may promote only as provider-neutral infrastructure.

## Rollback anchor
Rollback to base `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`. No mainline or sibling-branch merge is part of PREP.

## DEFER / REPLACE
DEFER concrete generation while no real backend is available or independently evidenced. REPLACE only the provider implementation when a backend is selected; preserve the provider/renderer contracts unless evidence shows the boundary is insufficient. DEFER image editing, streaming/progressive rendering, multimodal vision inference, and provider-specific optimizations to later isolated capabilities.
