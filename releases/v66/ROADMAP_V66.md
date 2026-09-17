# FAP Roadmap — V66 and Beyond

Base: `main` at `ee72c1068c643172118f6afdf7bd90e7efe29d16` (V65 operational staged canary + quarantine).

This roadmap keeps the existing fail-closed direction: candidate changes may be generated or discovered freely, but promotion toward `main` or production must require independently verifiable evidence.

## North Star

Build FAP into a compact, continuously improvable runtime that can:

1. discover or receive a capability proposal,
2. represent it as a non-executable specification,
3. build/evaluate it inside a trusted boundary,
4. bind all evidence to immutable content digests,
5. canary it through isolated stages,
6. rollback and quarantine regressions automatically,
7. promote only when evidence is reproducible,
8. keep enough provenance to explain exactly why a capability was accepted.

The objective is not unrestricted self-modification. The objective is **bounded autonomous improvement with reproducible promotion gates**.

---

## V66 — Independent Promotion Evidence

### Goal

Turn V65's staged canary/quarantine machinery into a promotion system whose evidence can be independently checked by CI and by a later integrator.

### Deliverables

- Add a CI workflow that runs the V66 validation gate on non-main integration branches.
- Introduce a machine-readable `EvidenceManifest` containing at minimum:
  - source commit SHA,
  - candidate digest,
  - test suite identifier,
  - test counts and result,
  - compile/static-check result,
  - synthetic canary result,
  - rollback result,
  - quarantine result,
  - timestamp/tool version metadata.
- Make promotion fail closed when the manifest is missing, malformed, stale, or does not match the candidate digest.
- Keep stage evidence isolated (5% / 20% / 50% / 100%); do not reuse earlier-stage evidence to satisfy later-stage gates.
- Add regression tests proving that tampered digest/evidence cannot promote.

### Acceptance gate

V66 is promotable only if:

- compile/static validation passes,
- the complete V66 test suite passes,
- warnings-as-errors passes,
- synthetic healthy candidate reaches 100%,
- synthetic bad candidate triggers rollback,
- repeated bad candidate reaches quarantine,
- evidence tampering tests fail closed,
- CI publishes the evidence artifact bound to the exact source SHA.

---

## V67 — Android End-to-End Runtime Path

### Goal

Verify that the control plane is useful on the real Android-facing path rather than only in synthetic host-side demos.

### Deliverables

- Build a deterministic Android/ADB integration harness around the existing Android state sync boundary.
- Verify candidate identity/digest survives host -> runtime -> Android state export.
- Add timeout/reconnect behavior for device disappearance.
- Add safe degraded mode: loss of verified telemetry must stop promotion, not guess success.
- Add checks that host slot paths, secrets, and internal filesystem locations are never exported to Android.
- Produce reproducible APK/instrumentation build evidence where the Android package participates.

### Acceptance gate

- Android build succeeds in CI.
- Host/device identity and digest round-trip matches.
- disconnect/reconnect tests pass.
- stale/unverified Android telemetry cannot advance a stage.
- exported state contains no prohibited local paths or secret material.

---

## V68 — Replay Corpus + Failure-Memory Evaluation

### Goal

Convert accumulated failures and regressions into a reusable evaluation asset instead of allowing the same class of error to recur.

### Deliverables

- Versioned replay-case schema.
- Convert `Failure Memory` / quarantine events into de-identified deterministic regression cases where possible.
- Separate development cases from holdout cases.
- Add capability-family metrics:
  - correctness,
  - latency,
  - timeout rate,
  - rollback rate,
  - repeated-regression rate.
- Prevent a candidate from passing solely by overfitting the cases used to generate it.

### Acceptance gate

A new candidate must not regress the retained replay corpus beyond an explicit budget, and promotion decisions must report both aggregate and capability-family results.

---

## V69 — Bounded Continuous Improvement Loop

### Goal

Close the loop from observed failure to proposed improvement without granting generated code uncontrolled host execution.

### Target loop

`observation -> failure classification -> non-executable capability spec -> SkillFactory handoff -> trusted isolated build/eval -> EvidenceManifest -> staged canary -> promote/rollback/quarantine`

### Required controls

- strict resource/time budgets,
- immutable candidate IDs,
- no candidate-selected host command,
- no direct write to `main`,
- no promotion without independent evidence,
- deterministic rollback target,
- bounded retry count to avoid pathological self-repair loops.

---

## V70 — Compact Knowledge/Capability Packaging

### Goal

Reduce RAM/storage cost while preserving useful behavior and provenance.

### Direction

- Content-addressed capability capsules.
- Immutable compressed payload + small mutable index.
- Sparse/lazy activation instead of loading all knowledge at once.
- Deduplicate repeated strings, metadata, test fixtures, and inherited release files.
- Separate exact-recall data from derived/semantic representations.
- Measure `bytes per retained capability` and `resident RAM per active capability`.
- Keep reconstruction boundaries explicit: lossy compression is allowed only where exact recovery is not required.

This is the stage where fly-like sparse routing / KC-style indexing can be tested experimentally, but only against measurable baselines rather than assumed efficiency.

---

## Main Integration Policy

A branch is not eligible for automatic `main` integration merely because it is newer.

Prefer selective integration when all of the following are true:

1. the change is not listener metadata only,
2. it adds a coherent capability or verified fix,
3. its source SHA and evidence are known,
4. tests/build checks pass independently,
5. no unresolved conflict or obvious regression exists,
6. generated artifacts do not overwrite unrelated mainline work,
7. rollback remains possible.

If any item is unknown, keep the candidate off `main` and record the missing evidence.

---

## Priority Order

1. **V66 CI + EvidenceManifest** — highest leverage; makes every later autonomous decision safer.
2. **Android build/runtime verification** — closes the largest reality gap between host-side demos and deployment.
3. **Replay corpus / Failure Memory** — stops recurring regressions.
4. **Bounded autonomous proposal loop** — only after independent validation is reliable.
5. **Compression/sparse capability packaging** — optimize size after correctness and provenance are measurable.

## Definition of Progress

Do not count branch count or generated code volume as progress. Count:

- independently passing gates,
- fewer repeated regressions,
- shorter verified rollback time,
- higher replay-corpus retention,
- lower RAM/storage per retained capability,
- more capabilities that can be promoted without human repair while preserving fail-closed behavior.
