# Goal Completion Loop candidate

Status: goal-loop core is merged to `main`; this document also describes the structured runtime wiring.

## Purpose

Turn FAP from a one-turn responder into a bounded goal-driven controller:

```text
user instruction
  -> goal
  -> plan
  -> execute
  -> critic
  -> replan if needed
  -> repeat
  -> stop only when the goal is satisfied or a guard boundary is reached
```

This candidate intentionally does not add Android/ADB behavior. It is a general orchestration layer.

## Added

- `GoalSpec`: objective, explicit success criteria and bounded autonomy limits.
- `PlannedAction`: a provider/tool-agnostic action contract.
- `ExecutionResult`: normalized execution outcome.
- `Critique`: completion/progress/retry/replan decision.
- `GoalCompletionLoop`: synchronous Plan -> Execute -> Critic -> Replan loop.
- `ConversationGoalRunner`: converts one chat instruction into a goal run.
- `JSONGoalStateStore`: checkpoint/resume without serializing executable code.

## Autonomous behavior

The loop continues without another user message when:

1. the critic says the goal is not yet satisfied;
2. there is measurable progress or a retryable alternate route;
3. the remaining action is inside the configured autonomy boundary.

It replans after failures or when the critic explicitly requests a new route.

## Hard stops

The loop stops instead of pretending to be infinitely autonomous when:

- success criteria are satisfied -> `completed`;
- maximum steps/replans are reached -> `exhausted`;
- too many failures occur -> `failed`;
- progress stalls -> `stalled`;
- the same action repeats too often -> `stalled`;
- execution is blocked -> `blocked`;
- an action requires approval and no approval is supplied -> `paused` (checkpointed and resumable).

These are deliberate safety and reliability boundaries, not intelligence claims.

## Intended integration

Existing FAP components can be injected behind the three contracts:

- Planner: V68 task planning / future LLM or local planning organ.
- Executor: current skill/runtime router and verified provider adapters.
- Critic: verification organ, tests, evidence gates, or an external reasoning model.

That allows FAP to remain small while routing hard reasoning to stronger models only when needed.

## Non-claims

This candidate does not make FAP an AGI and does not prove model-level intelligence. It adds the missing long-horizon control loop needed for “keep thinking and acting until done.”

It is synchronous. It does not run secretly or claim background execution.


## Structured runtime wiring

The main loop now has a concrete provider-neutral conversation entry point:

```text
one user instruction
  -> StructuredPlannerAdapter
  -> registered capability action(s)
  -> CapabilityRouterExecutor
  -> StructuredCriticAdapter
  -> satisfied?
       yes -> completed
       no  -> replan and continue
```

`AutonomousConversationRuntime` wires these pieces together. Planner and critic callbacks can be backed by a local model, a stronger online model, or a FAP router that selects between them. The executor only accepts explicitly registered capability kinds.

The planner receives bounded state summaries rather than an unrestricted execution surface. The critic receives the action result and explicit success criteria and must positively report satisfaction before the loop can claim `completed`.

Capability kinds configured in `approval_kinds` are forced into a checkpointed `paused` state before execution. Supplying an approval callback later resumes the same goal from its saved pending action.
