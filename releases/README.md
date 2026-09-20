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
- `v70/` — Concrete media provider adapters with bounded external command execution and validated artifacts.
- `v71/` — Interaction runtime routing chat, image, STT, TTS and half-duplex voice through the V69/V70 contracts.
- `v72/` — Audio lifecycle controls and bounded operational handling around the interaction stack.
- `v73/` — Provider capability probing and explicit readiness evidence.
- `v74/` — Health-gated interaction runtime that refuses media calls until provider probes allow them.
- `v75/` — Managed bounded chat with clear/undo/status controls, context budgets and response-storage clipping.
- `v76/` — Android Python packaging and verification for the current interaction stack.
- `v77/` — HTTPS image provider adapter with credential isolation, response-size bounds and schema/MIME/base64 validation.
- `v78/` — Gemma 4 Direct-Learning Integration (verified learned-state hashes, consolidated behaviour circuits, shadow memory, concept graph, V75/V71 chat/runtime integration).
- `v79/` — Creativity Success Learning (divergent operators, verified creative-experience lifecycle, replay protection, task-conditioned reuse, V78 composition).
- `V80 mainline addition` — Primitive Inventor + bounded Mini-IR sandbox + persistent Skill Registry + evidence-gated candidate/testing/shadow/active promotion loop (implemented in the V79 creativity package rather than a separate `v80/` snapshot).
- `v81/` — Local Adaptive Predictive Core (fixed reservoir, next-input predictive coding, bounded Hebbian overlay, verified counterexamples, replay-protected local learning, V79/V78 responder composition).
- `v82/` — Persistent Self-Generated Curriculum (capability map, weak-area selection, frontier-stretching tasks, independent sandbox verification, success-only structural compression, V80 primitive-loop bridge).

Future updates should be added as a new version directory unless explicit mainline integration is requested.
