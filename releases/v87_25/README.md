# FAP V87.25 — Structured Benchmark Reasoning Gateway

V87.25 rebases the structured-question work onto the verified V87.24 mainline.

The first GPQA Diamond measurement on V87.18 exposed a routing/contract failure:
- 198 questions × 4 shuffled repeats = 792 trials;
- answer-contract parse rate was 0%;
- measured accuracy was 0%;
- words such as `time`, `weather`, numbers, and `create` inside science questions could be misrouted into utility/builder organs.

V87.25 fixes that measurement layer without replacing or weakening existing FAP behavior.

## Structured lane

```text
explicit A-D contract
  -> separate benchmark instruction from question content
  -> parse A/B/C/D choices
  -> infer broad domain
  -> bounded native reasoning
  -> optional configured teacher only when explicitly enabled
  -> deterministic low-confidence unresolved fallback
  -> verify final Answer: $LETTER contract
```

The lane activates only when all four A-D choices and an explicit multiple-choice/answer contract are present.

All other requests delegate to the inherited V87.12 chat path unchanged. Existing weather, datetime, calculator, builder, memory, semantic-memory, adaptive-routing and code-generation behavior therefore remains behind the same compatibility boundary.

## Anti-gaming boundary

No GPQA answer key or benchmark-specific answer table is embedded.

When native FAP cannot resolve a question:
- it makes a deterministic choice from question + option content;
- the source is recorded as `unresolved_content_tiebreak`;
- confidence is 0.25;
- the internal verdict is `PARTIAL`, never `OK`.

This forced-choice fallback exists only to distinguish routing/output-contract correctness from semantic reasoning competence.

## Native verified reasoning in this stage

A narrow literal binary-arithmetic solver can independently verify simple numeric MCQs. More complex science, math and world-knowledge questions still require stronger native knowledge/reasoning organs or an explicitly enabled lawful local teacher.

## Compatibility with the latest mainline

V87.25 is based on V87.24 and leaves all V87.24 offline-bundle preparation and disconnected media inference paths unchanged.

Qwen is not used.

## Verification

GitHub Actions run **35590574347 — SUCCESS** on Python 3.11 and 3.12.

Per interpreter:
- V87.25 focused tests: **6/6 PASS**;
- inherited V87.02-V87.12 text regression suite: **96/96 PASS**;
- V87.22 offline-media regression suite: **6/6 PASS**;
- V87.24 offline-bundle regression suite: **5/5 PASS**.

GPQA Diamond run **35590580662 — SUCCESS**:
- questions: 198;
- shuffled repeats: 4;
- trials: 792;
- answer-contract parse rate: **100%**;
- measured accuracy: **208/792 = 26.26%**;
- ability route: `structured_mcq` for **792/792**;
- decision source: `unresolved_content_tiebreak` for **792/792**.

Therefore the GPQA result is approximately chance-level and is **not** evidence of GPQA-grade semantic reasoning. It verifies that the previous routing/format failure has been removed and that future knowledge/reasoning improvements can now be measured cleanly.
