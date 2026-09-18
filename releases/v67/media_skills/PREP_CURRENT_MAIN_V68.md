# Video Skill — current-main preparation addendum

Reviewed against main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68).

Next safe step: keep scene/timing plan deterministic and isolate actual rendering behind `VideoRendererAdapter`. Test missing renderer, timeout/error, empty/truncated artifact, wrong MIME/container, invalid duration/frame metadata and digest mismatch. A plan is not a generated video; generation claims require a concrete renderer independently exercised and the resulting container inspected.

Android: rendering may be host-side; declare network/storage implications and avoid broad storage permission. Bound duration/resolution/frame count, temp disk, peak RAM/CPU and wall time. Retain only explicit evidence fixtures; do not retain user source media by default.

Promotion requires reproducible renderer evidence and current-main regression. DEFER streaming, long-form rendering, GPU-specific assumptions and audio muxing. REPLACE if a proven renderer boundary already exists; sibling branches remain isolated.