# FAP V65 Release Report

## Objective

Move from V64's one-step canary A/B mechanism to an operational staged rollout that can consume Skill Factory file handoffs, accept only verified runtime telemetry, progressively increase exposure, roll back regressions, and quarantine repeated failures.

## Key invariants

1. Unverified telemetry never becomes canary evidence.
2. Evidence is isolated per canary stage.
3. Duplicate telemetry event IDs do not add evidence twice.
4. A candidate cannot jump from 5% directly to full rollout without passing the intervening stages.
5. The 100% state is reached after a healthy 50% stage; 100% does not incorrectly require a baseline traffic arm.
6. Regression triggers the existing verified rollback path.
7. Demotion and Failure Memory feedback occur only after rollback succeeds.
8. Duplicate rollback events do not inflate quarantine counts.
9. Quarantine can apply to a candidate digest or a repeatedly failing candidate family.
10. Android state export is sanitized and does not leak local managed-slot paths.
11. The sandbox client never lets candidate output select a host command.

## Validation executed

- `python -m compileall`: PASS
- `python -W error -m unittest discover -s tests -v`: **18/18 PASS** for the V65 delta suite
- trusted runner fixed-wrapper protocol test: PASS
- staged evidence isolation test: PASS
- malformed/unverified telemetry rejection tests: PASS
- candidate/family quarantine tests: PASS
- synthetic end-to-end mechanism demo: PASS

The local environment could not DNS-resolve github.com for a raw `git clone`, so the entire inherited V64 suite was not re-executed through a local clone. The GitHub V65 release is therefore built cumulatively from the existing V64 tree, while the newly added V65 delta is what was executed here. This limitation is recorded rather than hidden.

## Next target — V66

- real FAP runtime telemetry emitter integration
- signed/attested sandbox-wrapper responses
- canary evidence confidence intervals / sequential testing
- per-domain/capability rollout policies
- quarantine rehabilitation workflow requiring fresh holdout evidence
- automatic Skill Factory repair request after quarantine
- capability-matrix update from production evidence
