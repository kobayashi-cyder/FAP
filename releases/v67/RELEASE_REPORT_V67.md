# FAP V67 Release Report

## Release

**V67 — Native Repository Code Factory Stage 1**

## Purpose

Close the missing center of the autonomous development loop: produce real source-code candidates rather than only preparing, validating and promoting externally generated candidates.

## Closed-loop position

`Failure/CapabilitySpec -> Skill Factory request -> Native Repository Code Factory -> candidate manifest -> V62/V66 verification -> lifecycle -> canary -> rollback/quarantine -> repair request -> Native Repository Code Factory`

## Stage-1 implementation

- Safe structured Code IR -> Python source generation.
- Repository symbol/context index.
- SHA-bound, path-safe patch application.
- Diagnostic-driven missing-import repair.
- Bounded compile/test/repair loop.
- Hash-chained code-generation provenance.
- Non-executable candidate publication into existing Skill Factory handoff.

## Verified mechanism cases

- Generate a new Python function and satisfy its unit test.
- Detect a missing repository-local symbol and synthesize the required import.
- Repair two separate files over successive test rounds.
- Reject ambiguous symbol resolution.
- Reject unsupported failures rather than inventing a patch.
- Reject path escape, symlink workspaces, base-hash mismatch, patch-size excess and unsafe validation commands.
- Preserve original repository bytes.
- Detect lineage tampering.

## Known limits

- The current native planner does not translate arbitrary natural-language repository tasks into unrestricted AST edits.
- Missing-import repair is the first diagnostic repair strategy; additional compiler/test-error strategies are needed.
- Python is the Stage-1 language. Kotlin/Java/Gradle/TypeScript require dedicated repository parsers and repair strategies.
- OS/container isolation remains provided by the V66 trusted wrapper boundary, not by `LocalValidationRunner`.

## Validation

V67 delta: 28/28 tests PASS, compileall PASS, warnings-as-errors PASS, synthetic demo PASS.
