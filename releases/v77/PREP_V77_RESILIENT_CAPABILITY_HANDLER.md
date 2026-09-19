# V77 — Resilient Capability Handler candidate

Source main: `1a8e00d58f8adb5320737e8a20bb9cc4c8917624`.

## Capability
Adds an opt-in `ResilientCapabilityHandler` around existing FAP capability handlers. It converts handler exceptions into normal failed `ExecutionResult`s and retries only explicitly transient error tokens under a hard attempt bound (1–5). `needs_approval` is never retried.

## Why this candidate
The current autonomous runtime already bounds planning and routes only registered capabilities, but individual transient provider/tool failures can consume a goal-loop failure/replan without a cheap local retry. This layer improves failure handling without changing planner, critic, sparse routing, exchange registry, or provider contracts.

## Safety / compatibility
- opt-in wrapper; existing handlers are unchanged;
- no retries for approval-required actions;
- non-transient failures fail immediately;
- maximum attempts is capped at 5;
- no secrets, network dependencies, or generated-code activation;
- retry attempt count and exhaustion are surfaced as result metadata.

## Verification required before promotion
Run `python -m unittest candidates/goal_completion_loop/tests/test_resilient.py` plus the existing goal-completion-loop suite and relevant V66–V76 regressions. Compile the package on supported Python versions. Do not promote if retries duplicate irreversible side effects; such handlers must remain unwrapped unless they provide their own idempotency contract.

## Rollback
Discard branch `exp/v77-resilient-capability-handler` and return to source main SHA above. No persistent schema migration is introduced.

## Next expansion target
After independent verification, add an explicit idempotency/retry-safety declaration to capability registration so transient retry can be enabled by policy rather than manual wrapping.
