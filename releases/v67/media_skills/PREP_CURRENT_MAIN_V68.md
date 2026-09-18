# Image Skill — current-main preparation addendum

Reviewed against main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68); older V66/V67 assumptions are advisory only.

Next safe step: retain deterministic image request validation/render-plan generation and put real generation strictly behind an `ImageProviderAdapter`. Require negative cases for missing provider, timeout/error, malformed response, empty artifact, wrong MIME, impossible dimensions and SHA mismatch. Provider output must be independently decoded/inspected before claiming generation.

Android: adapter must declare network/storage implications; avoid broad storage permission and retain only user-requested artifacts/metadata. Measure bytes, dimensions, provider latency, peak RAM and temporary disk use. No prompt/artifact retention by default beyond explicit evidence fixtures.

Promotion requires a concrete provider adapter independently exercised with reproducible fixture/evidence plus current-main regression. DEFER editing/streaming/batch generation. REPLACE if a sibling-neutral foundation contract supersedes this interface; do not merge sibling branches automatically.