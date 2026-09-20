# V80 Release Report

## Scope

Implemented the first FAP adaptive-circuit loop combining sparse specialist routing, verifier-first gating, bounded circuit evolution and active success memory.

## Verification

Local Python 3.11 checks before push:

- compile: PASS
- adaptive-circuit unit tests: **10/10 PASS**

Repository CI additionally runs the V80 integration tests against the real V79/V78 code and regressions for V79, V78, V75 and V71.

## Safety / correctness properties

- Unverified circuits are unroutable.
- Duplicate verifier evidence is rejected.
- Failed/unverified outcomes are not stored in Active Memory.
- Mutated children are unroutable until benchmark-certified.
- Repeated failures quarantine and revoke circuits.
- Routing is deterministic for equal state and input.

## Limitation

V80 evolves routing/circuit parameters and specialist selection. It does not yet synthesize arbitrary executable circuit code. That remains behind the existing Primitive Inventor/Sandbox/Registry path and should be connected only after sandbox verification evidence can certify the generated implementation.
