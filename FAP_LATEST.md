# FAP latest development snapshot

Current additive development release: **V87 — Autonomous Improvement Core**.

Source, tests and integration notes are stored under [`releases/v87/`](releases/v87/).

V87 independently rebases the useful control-layer ideas from the Library handoff artifact `FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip` onto the current V86 mainline rather than copying its older duplicate subsystems.

V87 adds:
- `FAPEval` with per-ability scorecards and failure clustering;
- largest-failure-cluster targeting with V84 AbilityMap weakness as a tie-break;
- bounded V86 declarative Skill Evolution using eligible binding substitutions only;
- V86 Inventor + verifier/shadow promotion for repair proposals;
- benchmark-before, trial benchmark and settled benchmark-after;
- acceptance only when the target ability improves without reducing overall accuracy;
- quarantine of promoted but non-improving trial skills from V87 adoption;
- optional synchronization of accepted active skills into V82 sparse routing;
- independent FAP-Eval evidence fed back into V84 AbilityMap.

Source artifact provenance:
`SHA-256 660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7`.

The source archive was independently rerun: V82 tests **10/10 PASS**, V90 tests **6/6 PASS**. Its bundled TEST_REPORT states 7 V90 tests, but only six V90 unittest methods are present, so the observed 6/6 result is authoritative.

Core path:

```text
FAP-Eval
  -> failure cluster
  -> V84 weakness
  -> V86 invent/evolve
  -> verifier + shadow promotion
  -> trial benchmark
  -> accept or quarantine
  -> settled benchmark
  -> optional V82 sparse-route adoption
```

**Execution boundary:** V87 generates no arbitrary source code. Evolution changes only declarative references to host-owned, V86-eligible bindings.
