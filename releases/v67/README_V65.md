# FAP V65 — Operational Staged Canary + Quarantine

V65 extends V64's verified runtime dispatch and A/B rollback control plane into a staged operational rollout loop.

## Added

- `SkillFactoryHandoff`
  - atomic filesystem inbox/outbox handoff
  - accepts only non-executable capability specifications
  - binds candidate output to the SHA-256 of the claimed request
- `TrustedSandboxRunner`
  - fixed host-side runner argv
  - no shell
  - no `-c` inline execution
  - JSON stdin/stdout protocol
  - timeout and output limits
  - intended to invoke a separately trusted OS/container isolation wrapper
- verified runtime telemetry normalization
  - rejects unverified observations
  - validates candidate digest, arm, quality and latency
- `StagedCanaryController`
  - 5% -> 20% -> 50% -> 100%
  - evidence isolated by stage
  - no reuse of the 5% evidence to satisfy the 20% gate
  - 50% healthy stage promotes to full rollout
- `QuarantineLedger`
  - repeated candidate regression tracking
  - candidate-family regression tracking
  - duplicate failure events do not inflate counts
- `V65Coordinator`
  - verified telemetry -> stage evaluation
  - regression -> V63/V64 rollback path
  - successful rollback -> demotion/Failure Memory
  - repeated regressions -> quarantine
- `AndroidV65StateSync`
  - exports current canary/quarantine state without local slot paths

## Trust boundary

`TrustedSandboxRunner` is not itself a complete operating-system sandbox. It is a strict transport client to a preconfigured trusted wrapper/container boundary. Candidate output cannot choose the host command. The wrapper remains responsible for namespace/container/network/filesystem/resource isolation.

## Validation

- V65 delta compileall: PASS
- V65 delta unittest: **18/18 PASS**
- warnings-as-errors: PASS
- synthetic staged canary demo: PASS
  - 5% -> 20%
  - 20% -> 50%
  - 50% -> 100% complete
  - separate bad candidate -> regression -> rollback -> demotion -> quarantine
  - Android export contains no slot path

V64 and earlier release trees are inherited unchanged in the cumulative V65 release. Their previously recorded validation is preserved; the 18/18 figure above is the newly executed V65 delta suite in this environment.
