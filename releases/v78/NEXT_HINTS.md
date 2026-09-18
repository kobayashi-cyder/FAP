# FAP v78 next hints

Start from inherited main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15` and preserve the V77 adapter KEEP / real-generation DEFER boundary.

Priority: prove or reject one real backend through the existing bounded adapter without widening the trusted surface. Keep credentials runtime-only; sanitize evidence; bound payload, timeout, RAM and storage; preserve deterministic injected-transport tests.

Promotion gate: no statement that real image generation, Android integration, provider-specific compatibility, streaming, retries, or production latency/RAM/storage is supported until independently exercised. Run v78 focused checks plus V77, V75–V69 and V66–V68 regressions on Python 3.11/3.12. Android readiness additionally requires APK/AAB secret scan and device/emulator network/lifecycle verification.

Rollback: reset/discard v78-only work to inherited main `de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`.
