# Decision — V77 image HTTP adapter

Decision: DEFER real image generation claim; adapter candidate pending independent CI.

Implemented: safe bounded HTTPS image-provider boundary with environment-only bearer credential, response validation, deterministic injected-transport tests and latency measurement.

Not verified/claimed: any real provider/backend output, visual quality, provider-specific schema compatibility, Android network integration, streaming, retries, or production latency/RAM/storage. No provider secret is stored in this repository.

Promotion rule: adapter may become KEEP only after same-HEAD focused/core CI passes. Real generation remains DEFER until a real backend is independently exercised and its output evidence is recorded.

Rollback anchor: V76 `736029321620e418bb8c835291fbbcae47897645`; rollback by discarding/reverting the V77-only release/workflow files.
