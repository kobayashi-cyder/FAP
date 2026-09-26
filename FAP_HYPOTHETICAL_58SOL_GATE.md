# Hypothetical 5.8Sol Intelligence Gate

This name is an internal FAP project codename only. It does **not** claim
equivalence to an OpenAI model, including any future model named "5.8 Sol".

The purpose of this gate is to keep the test suite ahead of the implementation.
The ordinary regression suite can be 100% green while this aspirational gate
remains red.

## Promotion rule

A candidate passes only when **every** category passes. There is no weighted
average and no compensation between categories.

Required categories:

1. Procedurally generated multi-step quantitative reasoning.
2. Novel-symbol rule chaining with invented predicates and names.
3. Epistemic calibration on deliberately underdetermined premises.
4. Counterfactual rule replacement rather than repetition of the original rule.
5. Short-program execution reasoning with generated constants.
6. Paraphrase, choice-permutation, and irrelevant-distractor invariance.

For scored reasoning tasks, the answer must also:

- satisfy the structured answer contract;
- not come from the unresolved forced-choice fallback;
- receive an independently verified `OK` verdict;
- carry confidence >= 0.80.

## Anti-hard-coding properties

The dedicated CI injects a run-specific seed through
`FAP_HYPOTHETICAL_58SOL_SEED`. Constants, invented symbols, distractors, and
choice order therefore change across runs.

This is not a secret holdout: the generator is visible in the repository.
Future strengthening should add evaluator-owned sealed holdouts and external
benchmark sets that the implementation cannot inspect.

## Intended lifecycle

This gate is expected to fail before the corresponding general mechanisms are
implemented. Do not weaken, skip, mark expected-failure, or answer-key special
case the tests to obtain green CI. Fix the reusable reasoning, verification,
routing, calibration, and state mechanisms instead.
