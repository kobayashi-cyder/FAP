# FAP V68 Release Report

## Release

**V68 — TaskPlan AST Repair + Candidate Race Code Factory**

## Purpose

Move FAP's native coder from a single deterministic Stage-1 strategy toward a repository coding loop that can translate explicit implementation contracts into safe structured plans, propose multiple repairs, verify them independently, and promote only the best passing candidate into the existing autonomous capability pipeline.

## Closed-loop position

`CapabilitySpec / repair request -> TaskPlan -> repository context -> AST/Code-IR patch candidates -> isolated candidate race -> compile/test -> diagnostic repair -> winner patch -> candidate manifest -> V62-V66 verification/promotion -> canary -> rollback/quarantine -> repair request`

## Implemented repair families

- explicit pure-function generation from constrained natural language or structured request
- `NameError` missing symbol: direct import vs qualified-reference candidate race
- module `AttributeError`: repository-local re-export
- `ImportError: cannot import name`: repository-local re-export
- unexpected keyword `TypeError`: only when an explicit alias contract exists; rename-vs-alias candidates race under tests
- `SyntaxError: expected ':'`: only for mechanically identifiable compound-statement lines

## Selection rule

A candidate cannot win merely because it was generated first. Alternatives run on isolated copies. Non-passing alternatives are discarded. Passing candidates are ordered by: pass state, smaller changed-byte count, then lower validation latency. The winning patch is then re-applied to the canonical quarantine candidate and tested again in the next loop round.

## Safety properties

- source repository is never mutated by the code factory
- no shell execution and no `python -c`
- path/symlink/base-hash/patch-size checks remain inherited from V67
- arbitrary calls are rejected by the safe Code IR
- free-form natural language does not become arbitrary code
- ambiguous/unsupported diagnostics stop as rejected candidates
- code lineage remains hash-chained
- output remains non-executable until the existing verification/promotion stack accepts it

## Validation

V68 delta: **34/34 PASS**.
V67+V68 cumulative local suite: **62/62 PASS**.
compileall: PASS.
warnings-as-errors: PASS.
Synthetic integration demo: PASS.

The demo validates control mechanics only; it is not an external coding benchmark.
