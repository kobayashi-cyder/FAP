# PREP V77 — independent concrete image HTTP adapter candidate

Base / rollback anchor: `main` at `64619fbfe3967868a88085c4c4084ddcce4759ac` (V75). This preparation is intentionally independent of unintegrated V76 and must be rebased/rechecked if main moves before implementation.

## Goal
Prepare the smallest concrete image renderer/provider adapter candidate that can be promoted only with independent real-backend evidence. Existing `feature/v77-image-http-adapter` contains useful implementation material, but it is 8 commits ahead of V75 and includes V76 packaging changes; do **not** merge that branch wholesale. Selectively reimplement/cherry-pick only V77 image-adapter files onto current main.

## Expected files / interfaces
- `releases/v77/image_http/fap_image_http/adapter.py`: provider-neutral request/response contract plus one concrete HTTP provider adapter.
- `releases/v77/image_http/fap_image_http/__init__.py`: narrow exports only.
- `releases/v77/image_http/tests/test_image_http.py`: deterministic contract/negative tests with no live secret.
- `.github/workflows/v77-image-http-verify.yml`: unit/regression verification; live-provider evidence must be separate and explicitly identified.
- `releases/v77/DECISION_IMAGE_HTTP.md`: claim/evidence decision record.

Boundary: FAP core emits a bounded image request (prompt, dimensions/format where supported, timeout/resource limits). The provider adapter owns authentication, HTTP schema and provider-specific errors. A renderer/decoder boundary validates returned bytes/metadata before any capability claim. Core must not depend on provider-specific JSON.

## Required negative tests
Reject/handle: missing credentials; unreachable endpoint/DNS; timeout; HTTP 4xx/5xx/rate-limit; malformed JSON; missing image payload/URL; invalid or truncated image bytes; unsupported MIME/format; oversized payload/dimensions; redirect/download failure; provider success response with undecodable output. Verify secrets and prompt/output bytes are not written to logs by default.

## Android / host implications
No microphone/audio permission is introduced by V77. Network-backed rendering requires Android INTERNET/network availability when hosted in APK. Do not add broad storage permission: keep output in app-private/cache storage unless the caller explicitly exports it. Bound download size, decode dimensions, timeout and concurrent requests to avoid Android OOM/ANR. Provider credentials must not be embedded in APK assets.

## Privacy / retention defaults
Default retention is ephemeral: no prompt, credential, provider response body or generated image persisted by the adapter unless the caller explicitly requests a destination. Logs contain status/latency/byte counts and redacted error classes only. Document that a remote provider may have its own retention policy; adapter-local privacy cannot override provider policy.

## Resource evidence to capture
Record on the exact candidate SHA: end-to-end latency (p50/p95 where repeated), peak RSS delta during request+decode, returned compressed byte size, decoded dimensions/estimated decoded bytes, temporary/storage bytes, timeout behavior, and cleanup after success/failure. Android evidence should include no main-thread network/decode and bounded memory behavior on a representative device/emulator.

## Promotion evidence
Promotion may claim **real image generation** only if the exact candidate SHA independently executes one concrete provider/renderer adapter against a real backend and records: provider identity/config class (no secret), successful response, validated/decodeable image artifact with MIME/dimensions/size/hash, latency/resource metrics, and negative-path tests. Mock/fixture HTTP proves only adapter contract behavior, not generation. Preserve V69–V75 regression tests. If V76 integrates first, rebase and rerun rather than importing its packaging changes implicitly.

## DEFER / REPLACE
DEFER real generation claims when no live backend/credential/evidence is available; in that case V77 may only be described as provider-neutral HTTP adapter/lifecycle work. REPLACE the concrete provider module if its API/auth/licensing/availability changes, while preserving the provider-neutral contract and tests. DEFER video, STT, TTS, microphone lifecycle, audio focus, full-duplex, barge-in, echo cancellation, wake-word and streaming to later independent versions.

## Compatibility / independence
V77 must remain implementable directly from the rollback anchor without V76. Do not merge sibling `skill/media-*` branches. Media-lane changes, if any, stay on their own branches. Stop and refresh this PREP if main SHA changes or if the chosen provider cannot produce independently verifiable output.
