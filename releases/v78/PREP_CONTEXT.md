# FAP v78 preparation context

- Inherited branch: `main`
- Inherited main SHA: `eb75aad4be2d35cb376fb6750f772c00727934e4`
- Highest completed release on inherited main: `v77`
- Rollback anchor: `eb75aad4be2d35cb376fb6750f772c00727934e4` (discard/revert v78-only work)

## Changed surfaces
Main advanced after v77 without adding a completed v78 release. The new main wires one conversation/user instruction into the autonomous goal loop: structured planner, registered capability router, structured critic, bounded replanning, resumable approval checkpoints, and fail-closed planner/critic handling. The main commit reports Python 3.11/3.12 verification and no Android/ADB changes. Existing non-main v78 image-provider preparation remains relevant but is now secondary to validating the newly changed autonomous-loop surface.

## Compatibility constraints
Preserve the v77 bounded HTTPS image-provider adapter KEEP / real-backend DEFER boundary and its runtime-only credentials, response bounds and deterministic injected-transport behavior. Preserve the new autonomous-loop contracts: bounded replanning, capability registration/routing, resumable approvals, and fail-closed planner/critic behavior. Do not bypass approval checkpoints or silently fall back when planner/critic validation fails. Maintain V66–V77 regression behavior.

## Likely implementation targets
1. Focused v78 tests for instruction -> planner -> capability router -> critic -> bounded replan -> completion/approval-resume flow.
2. Persistence/restart evidence for approval checkpoints and bounded replan counters, including malformed planner/critic outputs and unavailable capability routes.
3. Trace/provenance linking the original instruction, plan revision, selected registered capability, critic result, approval state and final outcome without unbounded history.
4. Preserve the earlier real-image-backend probe as a separable experiment behind the v77 adapter boundary; do not let it widen the autonomous-loop trusted surface.

## Regression hazards
Unbounded replan loops; planner/critic schema drift; executing unregistered capabilities; approval bypass after restart; duplicated side effects on resume; fail-open handling; instruction loss or mutation; trace/history RAM growth; credential leakage or provider-specific coupling in the preserved image experiment.

## Android / packaging implications
The inherited main explicitly reports no Android/ADB changes. Keep v78 core work platform-neutral. If autonomous-loop state is later packaged for Android, persist only bounded resumable state, preserve approval semantics across lifecycle/restart, and avoid embedding provider credentials in APK/AAB/resources. Packaging/provenance should identify this exact main SHA. Android readiness still requires separate device/emulator evidence.

## Required verification
Run v78 focused autonomous-loop tests on Python 3.11/3.12: normal completion, bounded replan exhaustion, malformed planner output, malformed critic output, unknown/unregistered capability, approval pause/resume, restart/resume without duplicated side effects, and bounded trace/state growth. Then run v77 focused tests and V66–V76 regressions. If the preserved image-backend experiment is exercised, record sanitized real-backend evidence separately. Android claims require separate APK/AAB and device/emulator verification.

## Likely next planned experiment
Drive one deterministic instruction through a capability that requires approval, persist at the checkpoint, restart, resume exactly once, force one critic rejection/replan, and verify bounded completion plus provenance continuity. After that passes, return to the preserved v77 real-image-backend compatibility probe as an independent experiment.
