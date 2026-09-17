# FAP V66–V1000 Automation Plan

This file is a non-binding planning source for the scheduled FAP V1000 Runner. It does not authorize promotion to `main` by itself.

## Execution rule

For each version, re-check whether the planned experiment is still useful against the current repository. Work only on a non-main branch. End each attempted version with one of `KEEP`, `MODIFY`, `KILL`, `DEFER`, or `REPLACE`, with reproducible evidence, known limitations, and rollback information. Never advance only to increase the version number. If a version finishes early and is independently verified, the same run may continue to the next consecutive version.

## Phase plan

- V66–V100: evidence-first foundation — manifests, provenance, deterministic replay, negative/fault tests, CI, Android smoke tests, rollback drills.
- V101–V150: bounded memory — episodic/semantic/failure memory, dedupe, contradiction tracking, retrieval scoring, decay/retention.
- V151–V200: perception/state estimation — accessibility, screenshot/OCR fusion, temporal state graph, anomaly/unknown-state detection.
- V201–V250: planning — action schemas, preconditions/effects, bounded search, repair, cost/risk/uncertainty handling.
- V251–V300: Android execution — idempotent actions, package/focus recovery, watchdogs, multi-window, device profiles, soak tests.
- V301–V350: skill system — typed manifests, permission envelopes, registry, composition, quality scoring, deprecation.
- V351–V400: sparse/fly-inspired computation — sparse projection, KC-like expansion, WTA routing, associative recall, sparse-vs-dense benchmarks.
- V401–V450: distillation/compression — teacher traces, rules/FSM/adapters, quantization, dictionary/codon-like coding, competence-per-byte frontier.
- V451–V500: self-evaluation — critics, calibration, abstention, metamorphic/adversarial tests, hidden holdouts.
- V501–V550: trusted synthesis — capability specs, hermetic/fixed-command sandboxing, quotas, signing/provenance, auto-repair candidate tournaments.
- V551–V600: multimodal fusion — accessibility/text/pixels/events, conflict arbitration, modality confidence, adaptive sensor scheduling.
- V601–V650: continual learning — frozen core/mutable edge, adapters, replay, drift, plasticity budgets, learned-state rollback.
- V651–V700: multi-role architecture — planner/executor/verifier/curator/compressor, disagreement and evidence arbitration, overhead benchmark.
- V701–V750: device-aware runtime — CPU/GPU/NPU routing, local/remote split, low-RAM mode, cache tiers, battery/thermal budgets.
- V751–V800: formalized safety — typed effects, forbidden transitions, property tests, small-state model checking, fail-closed rules.
- V801–V850: knowledge substrate — compact concept graph, executable fragments, compressed indexes, contradiction sets, source confidence, aging.
- V851–V900: cognitive integration — working memory, attention/routing, global task state, goal arbitration, consolidation/sleep, closed-loop recovery.
- V901–V950: generalization/transfer — cross-app abstractions, few/zero-shot skill adaptation, analogy/subplan discovery, unseen-app holdouts.
- V951–V1000: hardening — multi-day soak, fault injection, migrations, stable APIs, resource caps, reproducibility packs, disaster recovery, final audit.

## Per-version experiment pattern

Use a five-release cadence for each topic when it remains useful: `Contract -> Prototype -> Break-it test -> Benchmark -> Gate`. Gate records the explicit decision and rollback proof. `KILL`, `DEFER`, and `REPLACE` are valid successful outcomes.

## Global evidence requirement

Every accepted experiment should bind source SHA, artifact digest, test results, runtime observations, relevant resource costs, rollback target, and limitations. Candidate self-report is not sufficient evidence. `main` is updated only by the separate integration review after it verifies the candidate is safe and useful.

## Starting point

V66 has already reached an implementation candidate and has been promoted to `main` as commit `d6329968a579fa0d20dbdb115a6f7a060d13a68e`. The next scheduled work should therefore reassess V67 against the current main state rather than redoing V66, unless a regression in V66 is discovered.
