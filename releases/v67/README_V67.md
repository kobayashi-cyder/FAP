# FAP V67 — Native Repository Code Factory Stage 1

V67 adds the first native repository code-generation path to the autonomous capability loop. It is intentionally constrained: it generates real Python code from a safe Code IR and performs deterministic repository repairs for supported runtime diagnostics instead of pretending to be a general-purpose coder.

## Implemented

- `RepositoryContextBuilder`
  - read-only Python repository scan
  - SHA-256 file and repository digest
  - top-level symbol index
  - relevant-file ranking
  - strict symlink and context-size rejection
- `FunctionIR`
  - native Python source generation from a restricted Code IR
  - arithmetic, comparisons, conditional expressions and a tiny pure-call whitelist
  - invalid identifiers, unknown variables, arbitrary calls and placeholders rejected
- `RepositoryPatchApplier`
  - full-file patches with optional base SHA-256 precondition
  - path-escape, symlink and patch-size rejection
  - deterministic patch-set digest
- `NativePatchGenerator`
  - safe-IR new-function generation
  - diagnostic-driven `NameError` missing-import repair
  - repository symbol must resolve uniquely before import generation
- `NativeRepositoryCodeFactory`
  - source repository is copied into a quarantine workspace and never modified directly
  - validation loop runs Python tests without shell or `python -c`
  - supported failures are repaired and re-tested for bounded rounds
  - unsupported failures stop as rejected candidates rather than fabricating a fix
  - successful output is a non-executable candidate manifest for the existing V62-V66 verification/promotion path
- `CodeLineageLedger`
  - hash-chained task/context/patch/test/repair/candidate provenance
  - tamper detection
- `V67CodeFactoryCoordinator`
  - connects non-executable Skill Factory requests to the native repository coder
  - publishes only candidates that reached `candidate_ready`

## Current generation capability

V67 Stage 1 can actually generate and repair code, but its scope is deliberately narrow:

1. Generate new pure Python functions from a verified structured Code IR.
2. Repair missing imports when a `NameError` symbol has exactly one repository-local definition.
3. Repeat repair/test cycles across multiple files.

It does **not** yet synthesize arbitrary multi-module implementations from unconstrained natural language. That is the next expansion target after the Stage-1 correctness boundary is stable.

## Safety / trust boundary

`LocalValidationRunner` is a validation transport for a pre-isolated workspace, not a complete OS sandbox. Production candidates must still continue through the V66 trusted sandbox/attestation and the existing static, holdout, resource, lifecycle and canary gates before activation.

V67 does not auto-commit generated code and does not activate generated code.

## Validation

- V67 delta unittest: **28/28 PASS**
- compileall: PASS
- warnings-as-errors: PASS
- synthetic integration demo: PASS
  - new function generated from Code IR -> tests pass
  - two repository files repaired across repeated validation rounds -> tests pass
  - source repository remains unchanged
  - lineage chain remains valid

The demo validates the code-factory mechanism only. It is not a public coding benchmark and not a Sol-parity claim.
