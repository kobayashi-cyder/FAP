# Decision — V77 image HTTP adapter

Decision: KEEP adapter layer; DEFER real image generation claim.

Implemented: safe bounded HTTPS image-provider boundary with environment-only bearer credential, response validation, deterministic injected-transport tests and latency measurement.

Independent verification: GitHub Actions run 35315469792 on implementation HEAD `175188ed84af371a45cfcb12822a1315707c0b1b` completed successfully on Python 3.11 and 3.12. Both jobs passed compile, V77 focused tests, V75–V69 focused regressions, and V66–V68 core regressions.

Not verified/claimed: any real provider/backend output, visual quality, provider-specific schema compatibility, Android network integration, streaming, retries, or production latency/RAM/storage. No provider secret is stored in this repository. Real generation remains DEFER until a real backend is independently exercised and its output evidence is recorded.

Rollback anchor: V76 `736029321620e418bb8c835291fbbcae47897645`; rollback by discarding/reverting the V77-only release/workflow files.
