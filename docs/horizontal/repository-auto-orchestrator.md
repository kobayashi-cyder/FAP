# Horizontal workstream: repository auto orchestrator

Branch: `horiz/repository-auto-orchestrator-20260924`

Status: experimental horizontal branch. Do not merge directly to `main`.

## Purpose

Close the gap between FAP's existing chat-to-coding bridge and its verification selector.

Before this workstream, callers could convert chat into a repository coding request and could separately derive focused/regression tests from a `PatchPlan`, but the caller still had to wire those stages together and manually carry the verification commands into execution.

This branch adds one bounded composition layer:

```text
chat instruction
  -> content-minimized ChatCodingRequest
  -> deterministic PatchPlan
  -> dependency-aware automatic verification selection
  -> repository digest stale-context guard
  -> existing detached-worktree coding coordinator
  -> verified candidate / rejected / blocked
```

## Added

- `PreparedAutoCoding`: immutable preparation artifact containing the exact chat request, plan and automatically selected verification commands.
- `AutoCodingOutcome`: normalized result with explicit `verified_candidate`, `rejected` or `blocked` state.
- `RepositoryAutoCodingOrchestrator.prepare()`: creates the plan and test selection without executing edits.
- `RepositoryAutoCodingOrchestrator.run()`: refuses to execute if repository context changed after preparation.
- `RepositoryAutoCodingOrchestrator.run_text()`: convenience path from one chat instruction to verified execution.
- plan-id and repository-digest consistency checks so a verification result from a different plan cannot be presented as verified.

## Boundaries

- No branch creation, promotion, merge, push or source-tree mutation is added here.
- Existing repository security policy, plan quality gate, detached-worktree executor, bounded repair loop and verification contracts remain authoritative.
- `main` and `master` remain rejected by the chat-coding contract.
- This branch does not claim model intelligence improvements by itself; it reduces manual orchestration and makes existing coding capabilities composable.

## Next horizontal extensions

The next useful workstreams after this layer are:

1. bounded multi-goal queueing with per-goal failure budgets;
2. capability-level telemetry that stores typed failure categories rather than raw sensitive output;
3. goal-loop adapter so the existing long-horizon controller can invoke this auto-coding orchestrator as a registered coding capability;
4. cross-language verification selection for JavaScript/TypeScript and shell edits;
5. benchmark harness measuring task completion, repair count, regression escapes and changed-byte efficiency.

Promotion should remain gated on dedicated CI plus compatibility checks against the current repository-coding mainline.
