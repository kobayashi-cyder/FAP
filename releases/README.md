# FAP release archive

Additive release snapshots are stored here without overwriting historical mainline files.

- `v61/` — Operational Capability Discovery.
- `v62/` — Verified Candidate Promotion Loop (sealed holdout, resource gate, evidence lifecycle, verified registry manifest).
- `v63/` — Verified Activation + Post-Activation Rollback (safe snapshot activation, verified runtime monitor, automatic rollback, provenance chain).
- `v64/` — Verified Runtime Dispatch + Canary A/B (load-time digest gate, trusted sandbox bridge, A/B rollback, demotion feedback, Android state sync).
- `v65/` — Operational Staged Canary + Quarantine (Skill Factory handoff, verified telemetry, 5/20/50/100 staged rollout, rollback quarantine, Android canary state).
- `v66/` — Attested Production Evidence + Statistical Canary Repair Loop (wrapper attestation, telemetry MAC, bounded statistical canary, evidence-gated quarantine release, automatic repair request, production Capability Matrix).

Future updates should be added as a new version directory unless explicit mainline integration is requested.
