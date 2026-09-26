# Horizontal workstream: fuzz

Branch: `horiz/coding-fuzz`
Integration target: `integration/coding-horizontal-v8781`
Release line: V87.81 (no version bump on this branch)

## Scope

Randomized coding/correction corpus generation and robustness testing.

## First deliverables

Generate non-hardcoded task variations, classify failure modes, preserve seeds and add regression cases.

## Non-negotiable integration contract

- Do not merge directly to `main`.
- Keep changes scoped to this workstream unless a shared contract is unavoidable.
- Preserve repository SHA preconditions, detached-worktree execution, explicit verification, bounded repair and no-direct-main-write behavior.
- Add focused tests for new behavior and keep horizontal CI green.
- Shared API/schema changes should coordinate through `horiz/coding-api-contract` or be documented before integration.
- Integrate into `integration/coding-horizontal-v8781` only after the workstream is coherent.

## Current state

Active. This manifest is the first dedicated push for the workstream and is the branch-local handoff point for parallel ChatGPT/coding-agent sessions.
