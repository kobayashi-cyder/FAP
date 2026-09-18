# Runtime wiring

This layer turns the verified goal-completion controller into a usable conversation-driven runtime.

## Flow

```text
instruction
  -> StructuredPlannerAdapter
  -> PlannedAction[]
  -> CapabilityRouterExecutor
  -> ExecutionResult
  -> StructuredCriticAdapter
  -> completed OR replan
```

The planner can only select explicitly registered capability kinds. The critic must positively confirm the supplied success criteria before the run becomes `completed`.

External or irreversible capability kinds can be configured as `approval_kinds`; those actions are checkpointed as `paused` before execution and can be resumed after approval.

Planner and critic are callable interfaces rather than a hard-coded model. This is intentional: FAP can route light work to a local model and difficult planning/evaluation to a stronger online model without changing the autonomous loop itself.
