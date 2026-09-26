# FAP V68 — TaskPlan AST Repair + Candidate Race Code Factory

V68 extends the V67 Native Repository Code Factory from deterministic Stage-1 generation/repair into a bounded planning and competing-patch loop.

## Added

- `NaturalLanguageTaskPlanner`
  - constrained natural-language contracts such as `function add(a,b) = a+b in calc.py`
  - Japanese form such as `関数 add(a,b) = a+b ファイル calc.py`
  - converts explicit expressions into the existing safe Code IR
  - unknown/free-form requests fall back to repair-only mode rather than fabricated source
  - structured requests support explicit compatibility contracts such as keyword aliases
- `AST patch planner`
  - append a generated function to a new/existing module
  - direct-import and qualified-reference alternatives
  - module re-export for supported `AttributeError` / `ImportError`
  - explicit-contract signature compatibility alternatives for unexpected-keyword `TypeError`
  - narrowly bounded `SyntaxError: expected ':'` repair when the source line is mechanically identifiable
- `DiagnosticRepairPlanner`
  - `NameError`
  - module `AttributeError`
  - `ImportError: cannot import name`
  - explicit-contract unexpected-keyword `TypeError`
  - safe `expected ':'` compile repair
- `CandidateRace`
  - every alternative patch is evaluated on an isolated repository copy
  - only passing candidates are eligible
  - among passing alternatives, smaller patches and lower validation latency are preferred
  - temporary race workspaces are deleted and their paths are not retained in evidence
- `V68CodeFactory`
  - TaskPlan -> initial AST patch -> test -> diagnostic candidate generation -> candidate race -> canonical winner -> re-test
  - source repository remains unchanged
  - generated candidate remains non-executable and enters the existing V62-V66 verification/promotion path
- `V68CodeFactoryCoordinator`
  - accepts only non-executable Skill Factory requests
  - publishes only `candidate_ready` manifests

## Safety boundary

V68 still does **not** treat arbitrary natural language as permission to synthesize arbitrary Python. Natural-language source generation is limited to an explicit pure-function grammar that is converted to the safe Code IR. Repair strategies are diagnostic-specific and bounded. Unsupported or ambiguous failures are rejected rather than guessed.

The local Python validation runner remains a transport for a pre-isolated workspace, not a full OS security sandbox. Production promotion still requires the V66 trusted wrapper/attestation and the existing static, holdout, resource, lifecycle, canary, rollback, and quarantine gates.

## Validation

- V68 delta unittest: **34/34 PASS**
- V67 + V68 local cumulative regression: **62/62 PASS**
- compileall: PASS
- warnings-as-errors: PASS
- synthetic V68 integration demo: PASS
  - constrained natural-language function generation
  - two-way NameError patch race
  - two-way signature compatibility race
  - mechanical compile-error repair

These are mechanism tests, not a public coding benchmark and not a Sol-parity claim.
