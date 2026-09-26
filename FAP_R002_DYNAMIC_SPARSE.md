# FAP r002 dynamic sparse intelligence candidate

This horizontal candidate extends the public r001 adaptive reasoning budget. It
does not change the stable \`VERSION\` on main.

## Goal

Make route selection itself adaptive instead of only increasing a numeric
reasoning budget.

The candidate implements:

- a small two-route active graph on ordinary tasks;
- bounded route-cap growth from the existing r001 difficulty budget;
- generic signal-to-specialist affinity;
- diversity pressure so near-duplicate routes do not occupy every slot;
- reserve routes activated by low confidence, verifier disagreement, missing
  verified evidence, or counterexamples;
- fail-closed verification aggregation;
- route-prior learning from verified outcomes only;
- deterministic tie-breaking and bounded values.

## Intended execution pattern

\`\`\`text
task signals
  -> r001 adaptive budget
  -> score specialist routes
  -> activate tiny cross-check graph
  -> execute / verify
  -> confidence good?
       yes -> stop
       no  -> activate reserve route(s)
  -> verified outcome
  -> bounded route-prior update
\`\`\`

This is a routing/control improvement. It is not evidence of GPT-5.6 Sol
parity, and the regression fixtures are mechanism tests rather than public
capability-benchmark results.

## Acceptance checks

Run:

\`\`\`bash
python -m unittest -v tests.test_fap_revision_r001 tests.test_fap_revision_r002
python -m compileall -q fap_revision_r001.py fap_revision_r002.py
\`\`\`

Promotion should remain blocked if regressions appear or if real task evaluation
shows no measurable gain.


## Hard-coding debt rule

Hard-coding is allowed when it accelerates discovery, debugging, or capability
growth, but it is never the intended terminal architecture.

Every hard-coded capability added during rapid iteration carries explicit
generalization debt. Before promotion to a stable mainline, overlapping
hard-coded branches should be reviewed for:

- consolidation into a shared abstraction;
- replacement of duplicated conditionals with generic routing/policy logic;
- migration of subject-specific constants or mappings into declarative data
  where practical;
- common verification and fallback contracts;
- removal of dead or superseded special cases;
- preservation of measurable behavior through regression tests.

The intended lifecycle is:

```text
rapid special-case implementation
  -> collect failures and successful patterns
  -> identify common structure
  -> merge overlapping implementations
  -> extract generic mechanism
  -> move variable knowledge/configuration to data
  -> regression/holdout verification
  -> delete redundant hard-coded branches
```

A large hard-coded implementation is acceptable as a temporary scaffold. A
stable release should not treat accumulated special cases as finished
generalization.
