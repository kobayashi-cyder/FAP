# FAP V66 Release Report

## Release

**V66 — Attested Production Evidence + Statistical Canary Repair Loop**

## Goal

Close the remaining V65 operational trust gaps between candidate execution and self-improvement decisions:

1. prove that a result came through the trusted wrapper path;
2. prevent candidate-authored JSON from impersonating verified runtime evidence;
3. prevent duplicate/stale evidence from biasing canary decisions;
4. avoid advancing candidates on statistically weak samples;
5. require new untouched holdout evidence to clear quarantine;
6. feed quarantine failures automatically back to Skill Factory;
7. retain verified production evidence in a descriptive Capability Matrix.

## Implemented modules

- `fap_autonomy/attestation.py`
- `fap_autonomy/telemetry_v66.py`
- `fap_autonomy/statistical_canary.py`
- `fap_autonomy/quarantine_release.py`
- `fap_autonomy/repair_bridge.py`
- `fap_autonomy/production_matrix.py`
- `fap_autonomy/v66_coordinator.py`

## Security / evidence changes

### Execution attestation

Every trusted-wrapper result can be bound to wrapper ID, nonce, slot tree SHA-256, result SHA-256, issue time, and HMAC-SHA256. Nonce mismatch, result tampering, expired attestation, untrusted wrapper ID, malformed digest, symlink slot, and inline runner code are rejected.

### Telemetry authentication

`FAPTelemetryEmitter` accepts a `VerifiedAttestation` object and authenticates the full telemetry row with a separate HMAC key. `V66Coordinator` verifies that telemetry MAC before any observation enters the Capability Matrix or canary controller. `attestation_id` is unique in the production matrix, preventing one verified execution from being replayed under multiple event IDs.

### Statistical canary

V66 keeps V65's 5/20/50/100 staged exposure but changes the decision rule: stage-specific evidence only; stale-stage observations rejected; decisions at `N, 2N, 4N...` checkpoints only; approximate non-inferiority confidence bounds for success, quality, and log-latency; conservative confidence allocation across three metrics and three A/B stages; inconclusive evidence remains monitoring.

### Quarantine release

A quarantined candidate/family can only be released with a new SHA-256-identified holdout evidence object that is verified, explicitly untouched, not previously used for a release, above minimum holdout score, and within allowed regression from baseline. A successful release deletes prior canary observations for that candidate and restarts at 5% so old evidence cannot satisfy the new rollout.

### Repair feedback

A rollback that reaches quarantine emits a non-executable Skill Factory repair request. The request requires new candidate bytes and a new untouched holdout verification cycle.

## Validation

- `python -m unittest -v tests.test_v66_operational`: **28/28 PASS**
- `PYTHONWARNINGS=error python -m unittest discover -s tests -v`: **64/64 PASS**
- `python -m compileall -q fap_autonomy examples tests`: PASS
- `python examples/run_v66_demo.py`: PASS

Synthetic integration results: healthy candidate 5% -> 20% -> 50% -> 100% complete; regressing candidate statistical rollback; quarantine and repair request; weak holdout release blocked; fresh untouched holdout release accepted; released candidate reset to 5%; production matrix retained 640 authenticated synthetic observations. These are control-path observations, not FAP capability benchmark results.

## Remaining gaps for V67

1. optional asymmetric signing / platform-backed key support;
2. direct real FAP Skill Bus/runtime telemetry hook;
3. sequential-safe/e-value style monitoring for longer canary windows;
4. capability-specific statistical policies;
5. explicit lineage quarantine -> repair -> candidate -> holdout -> rollout;
6. Capability Matrix -> Priority Engine with anti-volume bias;
7. Android safe V66 fields sync.
