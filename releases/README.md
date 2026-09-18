# FAP release archive

Additive release snapshots are stored here without overwriting historical mainline files.

- `v61/` — Operational Capability Discovery.
- `v62/` — Verified Candidate Promotion Loop (sealed holdout, resource gate, evidence lifecycle, verified registry manifest).
- `v63/` — Verified Activation + Post-Activation Rollback (safe snapshot activation, verified runtime monitor, automatic rollback, provenance chain).
- `v64/` — Verified Runtime Dispatch + Canary A/B (load-time digest gate, trusted sandbox bridge, A/B rollback, demotion feedback, Android state sync).
- `v65/` — Operational Staged Canary + Quarantine (Skill Factory handoff, verified telemetry, 5/20/50/100 staged rollout, rollback quarantine, Android canary state).
- `v66/` — Attested Production Evidence + Statistical Canary Repair Loop (wrapper attestation, telemetry MAC, bounded statistical canary, evidence-gated quarantine release, automatic repair request, production Capability Matrix).
- `v67/` — Native Repository Code Factory Stage 1 + Scoped Persistence Identity (safe Code IR source generation, repository context/symbol index, SHA-bound patching, diagnostic multi-round repair, hash-chained lineage, capability-scoped persistence migration/rollback).
- `v68/` — TaskPlan AST Repair + Candidate Race Code Factory (constrained NL/structured plans, AST alternatives, diagnostic repair families, isolated patch racing, non-executable verified handoff).
- `v69/` — Chat + Image + Audio Interaction Surface (bounded chat modes, provider-neutral image/STT/TTS boundaries, artifact validation/digests, half-duplex voice baseline; real providers remain separately evidenced).

Future updates should be added as a new version directory unless explicit mainline integration is requested.
