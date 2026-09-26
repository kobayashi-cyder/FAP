# r002 Intelligence Gap Repair Plan — 2026-09-26

Base: `side/fap-r002-dynamic-sparse-intelligence-20260925`

Latest inspected full Python sweep:
- 327 test files
- 326 passed
- 1 failed
- 99.694%
- failing file: `tests/test_fap_hypothetical_58sol_gate.py`

The failure is concentrated, not repository-wide. The six failing randomized families are:

1. multi-step quantitative transformations;
2. novel symbolic implication/exclusion chains;
3. epistemic underdetermination;
4. counterfactual replacement of an old rule;
5. small deterministic code-execution reasoning;
6. invariance under paraphrase, option permutation and irrelevant noise.

## Repair constraints

- No exact generated prompt, seed, option letter or answer may enter runtime routing/knowledge.
- Do not weaken the gate, lower confidence requirements, remove independent verification, or add an average-score escape hatch.
- Do not convert a failed derivation into a forced answer.
- Keep replay seeds only as diagnostics.

## General mechanisms to add or strengthen

### Structured multiple-choice boundary
Parse option labels and answer candidates separately from the question body. Solvers should return a semantic/numeric candidate first; option-letter mapping happens only after derivation.

### Ordered transformation solver
Represent sequential arithmetic operations as an explicit operation list and evaluate in order. Verification replays the list independently.

### Symbolic rule closure
Build a bounded implication graph for universal rules and a disjointness relation for exclusion rules. Derive only consequences licensed by the premises.

### Epistemic three-way decision
Separate `entailed`, `contradicted`, and `undetermined`. Existential premises such as "some B are C" must not be promoted to universal conclusions.

### Counterfactual scope override
When a prompt explicitly replaces an old rule for the current question, mark the old rule inactive in the local reasoning frame rather than letting both rules compete.

### Bounded code-semantics evaluator
For the gate's small deterministic Python subset, reason over a restricted AST / state transition model. Do not execute arbitrary repository or network code.

### Noise-robust subject isolation
Irrelevant declarative sentences must not overwrite the active task state. Option permutation must change only letter mapping, not the derived candidate.

## Verification contract

A gate answer is accepted only when:
- a candidate answer is produced by a task solver;
- a second verification path reproduces or validates the candidate;
- the final option mapping is unambiguous;
- confidence reflects evidence rather than a forced-choice fallback.

## Done condition

- all six randomized families pass on multiple fresh unpredictable seeds;
- no seed-specific patch exists;
- `tests/test_fap_hypothetical_58sol_gate.py` passes;
- `scripts/fap_test_sweep.py` returns 327/327 (or higher if new tests are added);
- historical V87 and current r001/r002 regressions remain green.
