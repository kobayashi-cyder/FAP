# Public FAP Gap Audit — 2026-09-26

Scope: `kobayashi-cyder/FAP` public repository only. The private repository is out of scope.

Baseline:
- default branch: `main`
- observed main HEAD: `6e95d39018d7229091229be7704db2ad4dfe4d4a`
- canonical public revision: `1.0.0-r001`
- reset-line policy: historical V87/V88 code may remain in the tree/history, but it is not automatically part of the active 1.x public release.

## P0 — release contract is internally inconsistent

Observed on main:
- `VERSION` is `1.0.0-r001`.
- `scripts/check_version_consistency.py` accepts only legacy two-component versions such as `87.81`.
- `.github/workflows/public-main-smoke.yml` expects `Stable mainline: **V<version>**`, while the reset README declares `Stable public base` and `Current revision`.
- `FAP_LATEST.md` still begins with V87.81 material although the active public line was reset to 1.x.

Impact: metadata checks can fail even when the reset-line release metadata is correct, and users can mistake historical V87 material for the active public release.

Repair branch:
- `side/public-ci-contract-repair-20260926`

Acceptance:
- one version parser supports `1.0.0-r001` and future three-component 1.x candidates;
- README/CHANGELOG/revision-module checks reflect the reset line;
- public smoke delegates to that contract;
- old V87 release text is clearly treated as historical rather than canonical 1.x metadata.

## P0 — r001 reasoning boundary is not hardened

Observed on main `fap_revision_r001.py`:
- non-finite confidence can be clipped incorrectly instead of forcing more verification;
- `int(signal.count)` may raise on non-finite or malformed values;
- malformed iterable entries can raise before a bounded budget is produced.

Impact: the smallest public reasoning gate is less robust exactly at external-input boundaries.

Repair branch:
- `side/public-r001-boundary-hardening-20260926`

Acceptance:
- NaN/inf confidence fails toward extra verification;
- malformed/non-finite signal metadata remains bounded and deterministic;
- ordinary valid behavior is unchanged.

## P0 — r002 generalization gate is the current measured intelligence bottleneck

Latest inspected full sweep on `side/fap-r002-dynamic-sparse-intelligence-20260925`:
- total: 327 test files
- pass: 326
- fail: 1
- score: 99.694%
- only failing file: `tests/test_fap_hypothetical_58sol_gate.py`

Inside that gate, six generalized randomized capabilities failed in the inspected run:
1. multi-step quantitative reasoning;
2. novel symbolic rule chains;
3. epistemic calibration / underdetermination;
4. counterfactual rule replacement;
5. code-execution reasoning;
6. paraphrase/permutation/noise invariance.

This is not a routing-only defect: the route mechanics and most regressions pass while answer construction / structured reasoning still fails under novel randomized instances.

Repair branch:
- `side/r002-intelligence-gap-repair-20260926`

Acceptance:
- no fixed answer/utterance exceptions;
- each of the six randomized families passes across fresh unknown seeds;
- verifier must distinguish a genuinely derived answer from a forced-choice fallback;
- results remain reproducible by emitting a replay seed after failure;
- full sweep remains green, not only the intelligence gate.

## P1 — dynamic sparse routing is not yet on public main

PR #163 is an open 1.0.01 candidate. Its CI is green, but it remains lateral and therefore is not the active public mainline.

Missing from current `main` release contract:
- learned dynamic-sparse route utility;
- task/capability/failure affinities;
- bounded beam search over route sequences;
- risk-driven re-densification;
- reusable generic routing state.

Acceptance:
- PR candidate is reviewed against reset-line versioning;
- measured regressions remain green;
- model-level capability claims remain evidence-gated.

## P1 — evaluation evidence is still weaker than the intelligence target

The repository correctly states that GPT-5.6 Sol-class performance is a target rather than a current claim. What is still missing for a defensible comparison:
- isolated unseen holdouts;
- multi-domain accuracy with sample counts;
- confidence calibration;
- routing/tool-selection accuracy;
- route-selection regret;
- latency and compute accounting;
- timeout/failure rate;
- contamination / answer-leak checks;
- frozen post-tuning confirmation runs.

Synthetic/random gates are useful but cannot establish external-model equivalence by themselves.

## P1 — speech is additive but not complete

PR #164:
- local TTS and bounded trainable prototype STT exist;
- open-dictation neural-grade STT is explicitly not claimed.

Issue #165 still calls for:
- malformed/empty WAV hardening;
- duration/model/training bounds;
- corrupt model JSON handling;
- silence handling;
- temp-file cleanup;
- current 1.x text-runtime wiring;
- real corpus/holdout metrics before stronger STT claims.

PR #166:
- Android continuous half-duplex voice is implemented and compile-verified;
- real-device behavior, barge-in/full duplex, echo cancellation, and similar claims need separate measured evidence.

## P1 — historical capability presence is not the same as active 1.x integration

The tree still contains many V87-era modules/tests. The reset README and CHANGELOG explicitly make 1.x the active public release line.

Therefore each historical capability needs one of three statuses:
- promoted into 1.x and release-gated;
- retained as legacy/reference only;
- removed/archived from the active surface.

Without this, tests can pass for historical code while the public release contract remains ambiguous.

High-value integration targets:
- repository coding agent and verifier;
- self-repair and rollback;
- long-horizon session continuity;
- retrieval/research with evidence;
- FCA bridge;
- media/image paths.

## P1 — coding workstreams remain open rather than consolidated

Open horizontal PRs include:
- symbol editing;
- JavaScript/TypeScript coding;
- test selection;
- release packaging;
- documentation coding;
- coding performance;
- coding benchmarks.

These should not be counted as active 1.x release capabilities until integrated and revalidated against the reset-line contract.

## P2 — release engineering / observability gaps

Still desirable:
- one machine-readable capability manifest for 1.x;
- one machine-readable evidence manifest tying each capability claim to tests/benchmarks and commit SHA;
- explicit supported Python/OS matrix;
- cold/warm latency budgets;
- memory/CPU ceilings;
- artifact provenance and rollback points;
- a single release gate that separates active 1.x tests from historical regression archives.

## Promotion policy

Do not merge a lateral branch solely because its focused test is green.

Minimum promotion gate:
1. targeted tests pass;
2. relevant regression tests pass;
3. release-contract check passes;
4. rollback point exists;
5. no answer-specific or benchmark-specific hardcoding;
6. benchmark claims include commit SHA, seed/dataset, sample count, wall time and failure count;
7. public-safe scope is preserved.
