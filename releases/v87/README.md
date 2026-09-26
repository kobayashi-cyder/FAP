# FAP V87 — Autonomous Improvement Core

V87 is the independent rebase of the Library handoff artifact **FAP V90 — Autonomous Improvement Core** onto the verified V86 mainline.

Source artifact SHA-256:

`660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7`

The source ZIP was re-executed independently: its V82 suite passed **10/10** and its V90 suite passed **6/6**. The ZIP's own TEST_REPORT claimed 7 V90 tests, but only six V90 unittest methods are present, so V87 records the observed 6/6 result rather than repeating the stale count.

## What was rebased

V90's duplicate Capability Map, Self Curriculum, Sparse Router and Skill Inventor prototypes were **not** copied over the newer mainline implementations.

V87 retains only the novel control-layer ideas and binds them to current components:

```text
FAP-Eval
  -> failure clusters
  -> V84 AbilityMap weakness
  -> RepairProposal
  -> V86 Generic Skill Inventor / Skill Evolution
  -> V86 verifier + shadow promotion
  -> trial benchmark
  -> accept or quarantine
  -> settled benchmark
  -> optional V82 sparse-route adoption
```

## Safety

- no arbitrary Python generation;
- Skill Evolution mutates only V86 declarative binding references;
- only V86 active/promoted skills can be trialed;
- post-change benchmark must improve the target ability without lowering overall accuracy before adoption;
- failed/non-improving trials are quarantined from the V87 adopted set;
- AbilityMap updates use independent FAP-Eval evidence.
