# FAP V66 — Attested Production Evidence + Statistical Canary Repair Loop

V66 extends V65's staged operational rollout with authenticated execution evidence, authenticated FAP telemetry, conservative statistical canary decisions, evidence-gated quarantine release, automatic Skill Factory repair requests, and production-evidence feedback into the Capability Matrix.

## Added

- `AttestedSandboxRunner` + `AttestationVerifier`
  - fixed absolute trusted-wrapper executable
  - `shell=False`; inline `-c` execution rejected
  - slot tree SHA-256 and symlink rejection
  - per-execution nonce
  - result SHA-256 binding
  - timestamp freshness checks
  - HMAC-SHA256 host-wrapper attestation
  - sanitized process environment
- `FAPTelemetryEmitter` + `TelemetryVerifier`
  - accepts only a `VerifiedAttestation` produced by the trusted verifier path
  - append-only JSONL with fsync
  - HMAC-SHA256 over the complete production telemetry row
  - telemetry-field tampering is rejected before canary ingestion
- `ProductionCapabilityMatrix`
  - accepts only verified, attested, authenticated production evidence
  - unique `attestation_id` prevents one execution from being counted multiple times
  - records success rate, quality, p95 latency, stage counts, candidate count, and control events
  - explicitly marked as operational evidence, not a public benchmark score
- `StatisticalStagedCanaryController`
  - 5% -> 20% -> 50% -> 100%
  - evidence remains isolated by stage
  - stale telemetry from an earlier stage is rejected
  - decisions only at bounded `N, 2N, 4N, ...` evidence checkpoints
  - approximate one-sided non-inferiority bounds for success, quality, and log-latency
  - conservative family-wise confidence allocation across 3 metrics x 3 A/B stages
  - statistically inconclusive evidence remains `monitoring` instead of being forced to advance/rollback
- `EvidenceQuarantineLedger`
  - candidate and family quarantine remain supported
  - quarantine release requires **fresh, verified, untouched holdout evidence**
  - holdout evidence SHA-256 cannot be reused for a later release
  - insufficient or regressed holdout evidence cannot clear quarantine
  - release resets canary evidence so old production observations cannot be reused
- `QuarantineRepairEmitter`
  - automatically emits a non-executable repair request when rollback causes quarantine
  - explicitly requires new candidate bytes, static safety, sandbox verification, no test weakening, no answer hardcoding, and new untouched holdout evidence
- `V66Coordinator`
  - telemetry MAC verification -> Capability Matrix -> stage-isolated canary -> rollback/demotion -> quarantine -> repair request
  - fresh holdout release -> canary reset -> new production evidence cycle

## Trust boundary

The V66 attestation is **HMAC-SHA256 symmetric host-wrapper attestation**. It is not hardware attestation, TPM attestation, or remote attestation. Its security depends on the HMAC key remaining inside the trusted wrapper/verifier boundary and never being exposed to candidate code.

`AttestedSandboxRunner` remains a client of an external trusted OS/container wrapper. The wrapper is responsible for actual filesystem/network/process/resource isolation. V66 does not pretend that a Python subprocess alone is a complete sandbox.

The telemetry HMAC key is separate from the sandbox-attestation key and belongs to the trusted FAP runtime/emitter boundary.

## Statistical interpretation

The canary gate uses conservative approximate normal bounds with finite decision checkpoints and a Bonferroni-style allocation across metrics/stages. It is intended as a practical regression-control mechanism. It is **not** a formal sequential clinical-trial procedure and does not establish model parity or benchmark superiority.

## Validation in this environment

- V66 delta unittest: **28/28 PASS**
- V65 + V66 local cumulative regression: **64/64 PASS**
- compileall: PASS
- warnings-as-errors: PASS
- synthetic V66 integration demo: PASS
  - authenticated host-wrapper attestation
  - authenticated FAP telemetry
  - 5% -> 20% -> 50% -> 100% healthy rollout
  - separate regressing candidate -> rollback -> demotion -> quarantine
  - automatic Skill Factory repair request
  - bad holdout release rejected
  - fresh untouched holdout release accepted
  - canary evidence reset after release
  - verified production evidence returned to Capability Matrix

The synthetic demo validates the control mechanism only. It is not an official benchmark and is not a Sol-parity claim.
