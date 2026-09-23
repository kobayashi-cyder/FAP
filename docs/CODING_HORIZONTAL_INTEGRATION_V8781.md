# FAP V87.81 Horizontal Coding Integration Policy

Integration branch: `integration/coding-horizontal-v8781`

This branch is the only collection point for the horizontal coding workstreams listed in `docs/CODING_HORIZONTAL_BRANCHES_V8781.md`. It is intentionally separate from `main`.

## Integration rules

1. **No horizontal branch merges directly to `main`.**
   Every `horiz/coding-*` branch targets `integration/coding-horizontal-v8781`.

2. **One capability per branch.**
   A branch may touch shared interfaces when necessary, but its primary purpose must stay within the branch registry.

3. **Green before integration.**
   A branch is eligible for integration only after the horizontal CI lane is green and its focused tests cover the new behavior.

4. **No leaf-to-leaf merges.**
   Shared work is merged into the integration branch first. Other workstreams then rebase or merge the latest integration branch into their own branch.

5. **Resolve conflicts on the leaf branch.**
   Do not use the integration branch as a conflict-resolution scratchpad.

6. **Keep V87.81 on horizontal branches.**
   Side branches do not bump `VERSION`, `FAP_LATEST.md`, or latest launchers merely to mark work-in-progress. Release numbering changes only when a coherent integration set is intentionally promoted.

7. **Fail closed on repository writes.**
   New coding features must preserve the existing planner SHA preconditions, detached worktree execution, explicit verification, bounded repair, and no-direct-main-write model.

8. **Shared contract changes are explicit.**
   Cross-cutting schema/API changes should first land through `horiz/coding-api-contract` or be documented in the integration PR before dependent branches consume them.

9. **Integration is selective.**
   The integration branch may take some horizontal branches and defer others. A branch existing does not imply it must be merged.

10. **Main promotion is a separate decision.**
    `integration/coding-horizontal-v8781` stays in Draft/WIP form until the selected set is coherent, green, documented, and reviewed as one release candidate.

## Recommended per-branch flow

```text
main V87.81
   |
   +--> integration/coding-horizontal-v8781
             |
             +--> horiz/coding-<workstream>
                       |
                       +--> focused implementation
                       +--> focused tests
                       +--> horizontal CI green
                       |
                       +--> PR -> integration/coding-horizontal-v8781
                                  |
                                  +--> aggregate regression
                                  +--> selected integration
                                  |
                                  +--> separate promotion decision -> main
```

## Collaboration rule for multiple ChatGPT sessions

A session should claim one horizontal branch, fetch the current integration head before starting, and keep its commits scoped. When another branch lands upstream, sync from the integration branch rather than pulling commits directly from another leaf branch. This keeps ownership and conflict history legible.
