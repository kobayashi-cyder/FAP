# Video Generation Skill — PREP

Status: non-main experimental lane.

## Guaranteed scope
- Validate scenes, dimensions, FPS and format.
- Compile a deterministic scene-to-frame render plan.
- Refuse to claim rendered video when no renderer is configured.
- Verify returned artifact is non-empty video media and expose digest evidence.

## Renderer strategy
A Remotion-compatible adapter is a strong candidate for deterministic programmatic rendering. Keep the FAP skill contract renderer-agnostic so Remotion, local ffmpeg pipelines, or future providers can be swapped without changing the planner.

## Next implementation steps
1. Add render-plan JSON schema/versioning.
2. Add assets/captions/audio-track references with digest pinning.
3. Add renderer timeout/cancellation/resource budgets.
4. Add Remotion adapter in an isolated sub-branch; render only from fixed inputs and pinned assets.
5. Add output metadata verification: duration, dimensions, frame rate and container.

## Promotion evidence
- deterministic frame plan tests;
- invalid timing/FPS/dimension tests;
- renderer failure/wrong-MIME tests;
- clean-checkout render of a short fixture;
- measured render latency/RAM/storage;
- no external asset silently changes without digest/provenance update.

Local prototype verification before upload: combined media prototype suite 12/12 PASS. Actual video rendering is not claimed until a renderer adapter is independently verified.
