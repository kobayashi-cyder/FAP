# FAP V87.12 — Semantic Long-Term Memory + Adaptive Routing

V87.12 replaces the V87.11 strategy of retaining a large raw chat window with a smaller 48-turn raw window plus compact semantic state.

## New organs

- Semantic long-term memory: explicit goals, constraints, preferences, selected facts, verified task experiences.
- Semantic compaction: repeated/paraphrased entries merge; low-value noise is not promoted.
- Preference supersession: newer explicit values replace older current-state values while retaining a tiny previous-value trace.
- Adaptive routing ledger: verified route outcomes create bounded family-level priors.
- Routing safety locks: explicit strong intents cannot be overridden by learned priors.

## Preserved

V78 distilled circuits, V87.07 specification compiler, V87.10 Program IR code synthesis, V87.11 multi-intent orchestration, candidate deliberation, coverage critic, goal/constraint ledger, optional Gemma4:E2B teacher fallback. Qwen is not used.

## Design boundary

This is deterministic semantic compression and outcome learning, not neural-weight learning and not a claim of GPT-5.6 Sol-level general intelligence.
