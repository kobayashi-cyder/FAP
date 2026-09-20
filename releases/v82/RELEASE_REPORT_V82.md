# V82 Release Report

## Scope

V82 combines sparse specialist routing, verifier-first gating, bounded neuroevolution-style mutation and success-only active memory, while integrating the current V80 and V81 mechanisms.

## Verification targets

- adaptive-circuit unit suite: 10 tests
- V80 Primitive bridge suite: 4 tests
- V81 Local Adaptation bridge suite: 4 tests
- V79/V81/V78 composition suite: 3 tests
- Python 3.11 and 3.12 in repository CI
- V81, V79, V78, V75 and V71 regression suites

## Correctness properties

- Unverified or quarantined circuits are unroutable.
- Low-relevance circuits remain inactive even when top-k slots are available.
- Duplicate verifier evidence is rejected.
- Failed/unverified outcomes do not enter Active Memory.
- Mutated children are unroutable until independently certified.
- Repeated circuit failures can revoke execution rights.
- Routing is deterministic for equal state and input.
- V80 primitives below `active` are never adopted.
- V80 `active` primitives are rechecked from recorded unit/boundary/determinism/timeout/shadow evidence.
- V81 passive certification does not mutate verified learning state or the fixed reservoir.
- V81 local guidance is generated only when the shared sparse router selects it.

## Execution boundary

V82 can route and execute V80 bounded Mini-IR primitives and can selectively invoke V81/V79 specialist mechanisms. It does not grant arbitrary generated Python/native code execution rights.
