# FAP 1.0.01 General Reasoning Side Branch

Branch: `side/1.0.01-general-reasoning-core-20260926`

This document records what the side branch actually implements and what remains
unproven. It is intentionally stricter than a feature checklist.

## Implemented on this side branch

- generic dependency-aware problem decomposition;
- multi-lane candidate generation;
- fail-closed multiple-choice behavior when no answer is verified;
- independent arithmetic recomputation;
- independent deterministic-physics formula recomputation;
- fresh rule replay with evidence identity checks;
- fresh symbolic derivation replay and countercheck;
- fresh grounded-retrieval replay;
- one-variable linear-equation solving with substitution verification;
- conservative evidence-aware confidence calibration;
- risk-adaptive sparse-to-dense search policy;
- repeated independent verification for higher-risk tasks;
- user-subject priority over assistant-generated context;
- automatic chat/tool/coding channel selection from task decomposition;
- answer-isolated external holdout evaluator with accuracy, coverage,
  abstention, Brier, ECE and latency metrics.

## Current internal generated evidence

The generated reasoning holdout currently contains 51 cases per seed:

- 12 generated arithmetic cases;
- 10 generated Ohm-law cases;
- 12 generated one-variable linear equations;
- 8 unknown-item abstention cases;
- 6 contextual rule-reasoning cases;
- 3 symbolic derivations.

A multi-seed stress run completed 8 rounds / 408 cases with 408 passes and a
worst-round score of 1.0.

This validates these generated mechanisms only. The generators and supported
task families are known to the repository, so this is not an independent
general-intelligence benchmark and is not evidence of GPT-5.6 Sol equivalence
or superiority.

## External evaluation boundary

`fap_1x_external_eval.py` requires the answer-key file to live outside the
repository tree. Runtime inference completes before scoring reads the answers.
Reports record:

- commit SHA;
- prompt and answer-set SHA-256 hashes;
- aggregate and per-domain accuracy;
- coverage and abstention;
- answered-only accuracy;
- Brier score;
- 10-bin ECE;
- mean / p50 / p95 / max latency.

No broad external benchmark result is claimed until such a dataset is actually
executed under a frozen commit and reproducible conditions.

## Still missing for a credible GPT-5.6 Sol-class comparison

### P0 — learned general representation / generation

The side branch still relies mainly on explicit symbolic solvers, local
knowledge, retrieval, rules and structured hypothesis generation. It does not
yet contain a broadly trained language representation/generator comparable to
a frontier language model.

### P0 — broad unseen task distribution

Real external holdouts such as broad knowledge, difficult science, mathematics,
coding/repository repair, long-document reasoning and adversarial tasks have not
yet been measured here.

### P0 — learned transfer to novel abstractions

The current generic algebra and decomposition layers improve transfer, but FAP
does not yet demonstrate robust formation of new reusable abstractions from
many unrelated unseen tasks.

### P0 — strong independent coding benchmark

Repository coding has a verified execution contract and auto-routing, but no
external SWE-style or HumanEval-style result is claimed.

### P1 — true learned route creation

Dynamic sparse routing learns route utilities and topology behavior, but new
reasoning operators are not yet learned from data and synthesized into the
runtime as validated reusable operators.

### P1 — multimodal general reasoning

Android, image/media and speech boundaries exist, but broad image/document/UI
reasoning has not been evaluated against an external multimodal holdout.

### P1 — empirical confidence calibration

The current confidence calibrator is conservative and evidence-aware. Its output
is not a calibrated probability claim until fitted/validated on an external
calibration set.

## Promotion rule

Do not merge this side branch merely because internal tests are green. Promotion
requires review of the code diff, a frozen side-branch commit, and preferably at
least one genuinely external answer-isolated evaluation. Main remains unchanged
until explicitly promoted.
