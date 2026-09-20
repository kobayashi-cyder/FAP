# V81 Release Report

## Scope

Implemented a FAP adaptive-circuit layer combining sparse specialist routing, verifier-first gating, bounded neuroevolution-style mutation and success-only active memory. V81 also connects the V80 Primitive Inventor/Sandbox/SkillRegistry loop to sparse runtime routing.

## Verification targets

- adaptive-circuit unit suite: 10 tests
- V80 Primitive bridge suite: 4 tests
- V79/V78 integration suite: 3 tests
- Python 3.11 and 3.12 in repository CI
- V79, V78, V75 and V71 regression suites

## Correctness properties

- Unverified circuits are unroutable.
- Duplicate verifier evidence is rejected.
- Failed/unverified outcomes do not enter Active Memory.
- Mutated children are unroutable until independently certified.
- Repeated failures quarantine and revoke circuits.
- Routing is deterministic for equal state and input.
- V80 primitives below `active` are not adopted.
- V80 `active` primitives are rechecked from recorded unit/boundary/determinism/timeout/shadow evidence before V81 certification.

## Remaining boundary

V81 mutates circuit routing parameters and can execute V80's bounded Mini-IR primitives. It does not yet evolve arbitrary unrestricted Python or native code; executable invention remains deliberately constrained by the V80 Mini-IR sandbox.
