# r002 Integration Blockers — 2026-09-26

Target base: `integration/public-1.0.01-ready-20260926`

This branch intentionally stages only additive r002 reasoning/evaluation material.
It must not overwrite the 1.0.01 release contract, launchers, gateway, or VERSION.

Known promotion blocker:
- `tests/test_fap_hypothetical_58sol_gate.py` still fails randomized generalization families.

Required before promotion:
1. multi-step quantitative reasoning passes fresh seeds;
2. novel symbolic rule closure passes fresh seeds;
3. epistemic underdetermination is distinguished from entailment/contradiction;
4. counterfactual rule replacement scopes correctly;
5. bounded code-execution reasoning passes without arbitrary execution;
6. paraphrase / option permutation / irrelevant noise invariance passes;
7. full test sweep is green;
8. no answer-, seed-, or benchmark-specific hardcoding is added;
9. release-contract and r001 boundary tests remain green.

This branch is therefore suitable for continued repair and review, but not yet
for promotion into the public 1.0.01 integration spine.
