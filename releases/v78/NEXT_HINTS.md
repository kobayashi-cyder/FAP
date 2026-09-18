# FAP v78 next hints

Start from inherited main `eb75aad4be2d35cb376fb6750f772c00727934e4`. Highest completed release remains v77; v78 preparation must therefore absorb the post-v77 autonomous-goal-loop change rather than replay an obsolete intermediate listener plan.

Priority: verify instruction -> structured planner -> registered capability router -> structured critic -> bounded replan, with resumable approval checkpoints and fail-closed invalid planner/critic handling. The strongest first experiment is approval pause -> persistence -> restart -> single resume, followed by one forced critic rejection and bounded replan, proving no duplicate side effect and continuous provenance.

Preserve still-relevant non-main work: v77 bounded HTTPS image adapter remains KEEP while real backend generation remains DEFER. Keep the real-backend probe separate and secondary; runtime-only credentials, sanitized evidence, bounded payload/time/RAM/storage, and deterministic injected-transport tests remain mandatory.

Promotion gate: Python 3.11/3.12 focused v78 checks for normal completion, malformed planner/critic, unknown capability, bounded replan exhaustion, approval pause/resume, restart idempotence and bounded state/trace; then v77 and V66–V76 regressions. No Android readiness claim without separate APK/AAB and device/emulator evidence. No provider/backend production claim without real-backend evidence.

Rollback: reset/discard v78-only work to inherited main `eb75aad4be2d35cb376fb6750f772c00727934e4`.
