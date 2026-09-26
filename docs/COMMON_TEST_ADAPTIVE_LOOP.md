# Common Test Adaptive Loop (non-hardcoded)

This document defines how FAP 1.0.0 may improve over repeated Common Test benchmark rounds without memorizing question-specific answers or adding utterance/question-specific branches.

## Goal

Improve score by changing generic reasoning behavior, not by storing the benchmark answers.

A benchmark item, question ID, exact wording, correct option, or answer-specific rule MUST NOT be written into runtime knowledge, routing, solver code, prompts, or memory.

## Six-round protocol

Round 0 is the frozen baseline. Rounds 1-5 may adapt only generic policies. Round 6 is a frozen confirmation run with no further adaptation.

Each adaptive round follows this loop:

1. Execute the benchmark under a fixed wall-clock budget.
2. Record only abstract failure evidence.
3. Classify failure modes.
4. Propose one or more generic policy changes.
5. Replay on development slices and regression suites.
6. Promote only changes that improve aggregate score without violating holdout, latency, or regression gates.

## Allowed learning signals

The adaptive controller may retain only generic features such as:

- subject family (language / mathematics / science / social science / information);
- task form (reading, symbolic derivation, numerical calculation, graph/table interpretation, multi-step selection);
- failure class (parse, retrieval, decomposition, arithmetic, logic, evidence selection, option elimination, verification, timeout);
- confidence and verifier disagreement;
- elapsed time and reasoning-budget exhaustion;
- number of candidate branches and verifier checks;
- whether a generic tool/solver would have been useful;
- aggregate accuracy/latency statistics for a capability class.

## Forbidden learning signals

Do not retain or compile into runtime behavior:

- exact question text;
- question-number-specific rules;
- exact correct choices or answer strings;
- question fingerprints mapped to answers;
- handwritten exceptions for a named exam item;
- benchmark-only lookup tables;
- hidden answer-key access during inference.

## What may change between rounds

Only reusable mechanisms may be adapted:

- routing weights among reasoning paths;
- dynamic sparse branch count;
- per-task reasoning budget;
- verifier depth and counterexample search depth;
- decomposition depth;
- symbolic/numeric solver activation thresholds;
- reading-window allocation;
- confidence calibration;
- generic option-elimination strategy;
- memory retrieval breadth;
- failure-router priorities.

All knobs require hard caps so a score increase cannot be purchased with unbounded compute.

## Error-driven adaptation

For each wrong answer, convert the event into an abstract signature, for example:

```text
subject=math
task=multi_step_numeric
failure=verification_missing
confidence=0.78
verifier_disagreement=true
timeout=false
```

The signature may increase future verifier depth for the class `multi_step_numeric`, but it may not contain the original problem or answer.

## Dynamic compute rule

Keep easy items sparse. Densify only when generic risk signals rise:

```text
base path
  -> low confidence? add alternate path
  -> verifier disagreement? add independent verifier
  -> counterexample found? reopen decomposition
  -> time budget nearly exhausted? stop and return best verified candidate
```

This lets later rounds spend more compute where prior rounds reveal generic weakness while preserving speed on easy items.

## Promotion gate

A change is promoted only when all conditions hold:

1. Development aggregate score improves or remains equal with lower compute.
2. No protected subject regresses beyond the configured tolerance.
3. Unseen holdout score does not regress.
4. Latency and compute remain within fixed caps.
5. Existing non-benchmark regression tests still pass.
6. No answer leakage or item-specific branch is detected.

Unmeasured and unverified changes are not promoted.

## Recommended six-run interpretation

- Run 1: baseline and failure taxonomy.
- Run 2: routing and decomposition adaptation.
- Run 3: verification and counterexample-depth adaptation.
- Run 4: subject-family solver/tool routing adaptation.
- Run 5: confidence calibration and compute reallocation.
- Run 6: frozen confirmation; no learning from this run is used to claim its score.

The objective is monotonic generalization, not monotonic score on one repeatedly exposed answer set.

## Benchmark integrity

The final benchmark set must be fingerprinted and isolated before tuning. Development and final holdout must not share answer-bearing artifacts. A benchmark score is reported together with wall-clock time, item count, per-subject score, timeout count, compute budget, and commit SHA.

A higher score on a repeatedly exposed set is not sufficient evidence of improved intelligence; promotion requires improvement on an unseen or otherwise isolated holdout.


## FAP 1.0.01 routing implementation

The reusable dynamic-compute policy above is implemented by the public
`fap_dynamic_sparse_routing.py` candidate. It begins with a mildly dense graph,
then learns node utility and route-transition utility, sparsifies routine work,
and can re-densify or rewire the graph when uncertainty, novelty, verifier
disagreement, or reusable failure evidence rises.

The router stores only generic routing state; benchmark item text and answers
remain forbidden learning signals.
