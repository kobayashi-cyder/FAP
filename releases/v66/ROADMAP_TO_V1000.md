# FAP Roadmap — V66 to V1000

## Purpose

This roadmap treats version numbers as experimental checkpoints, not as feature-count inflation. Every release should add one measurable capability, one measurable reliability improvement, or one evidence-producing experiment. A version may legitimately conclude that an idea should be rejected.

The long-term target is not a vague claim of "human-level" or "GPT-level" intelligence. The target is a compact, auditable, adaptive system that can perceive, remember, plan, execute, evaluate, compress experience, and safely improve selected components under explicit resource and safety constraints.

## Global promotion rule

Every version should produce an EvidenceManifest binding source SHA, artifact digest, test results, runtime observations, resource cost, rollback target, and known limitations. Promotion requires reproducible tests, no unresolved regression on the protected holdout set, and a valid rollback path. Self-reported success from candidate code is never sufficient by itself.

| Version range | Primary theme | Representative milestones | Exit condition |
|---|---|---|---|
| V66–V100 | Evidence-first foundation | V66 EvidenceManifest; V70 deterministic replay; V75 negative-test suite; V80 CI matrix; V85 dependency/SBOM checks; V90 Android E2E smoke path; V95 rollback drills; V100 foundation freeze | Reproducible promotion/rollback with independent evidence |
| V101–V150 | Memory architecture | Episodic/event memory, semantic memory, Failure Memory normalization, dedupe, TTL/decay, retrieval scoring, contradiction tracking, provenance | Useful retrieval improves tasks without unbounded memory growth |
| V151–V200 | Perception and state estimation | Screen segmentation, text/OCR fusion, accessibility-tree fusion, temporal differencing, confidence maps, UI-state graph, anomaly detection | Stable state estimate from noisy Android observations |
| V201–V250 | Planning core | Goal decomposition, action schemas, preconditions/effects, bounded search, plan repair, time/cost budgets, uncertainty-aware planning | Plans can be replayed, audited, repaired, and scored |
| V251–V300 | Android embodied execution | ADB/accessibility action arbitration, app recovery, focus recovery, task watchdogs, idempotent actions, multi-window handling, device capability profile | Long-running Android tasks recover from common failures autonomously |
| V301–V350 | Skill system | Declarative skills, skill signatures, capability contracts, skill composition, permission envelopes, versioned skill registry, skill deprecation | Skills are reusable without arbitrary host execution |
| V351–V400 | Sparse / fly-inspired computation | Sparse projection, KC-like expansion, winner-take-most routing, locality-sensitive codes, associative lookup, event-driven updates, sparsity sweeps | Demonstrated memory/latency benefit on defined tasks vs dense baseline |
| V401–V450 | Distillation and compression | Teacher trace capture, behavior distillation, symbolic trace compression, quantization experiments, adapters, dictionary codes, reversible/irreversible compression comparisons | Smaller runtime preserves defined task competence within measured loss |
| V451–V500 | Self-evaluation | Critic models/rules, calibration, uncertainty estimates, metamorphic testing, adversarial task generation, counterexample memory, confidence gating | System can detect a useful fraction of its own failures before execution |
| V501–V550 | Trusted sandbox and synthesis | Restricted code synthesis, capability-spec handoff, hermetic runners, filesystem/network caps, resource quotas, artifact signing, provenance chains | Candidate-generated components can be tested without trusting them |
| V551–V600 | Multimodal fusion | Text, UI tree, image patches, audio/event inputs where available, cross-modal alignment, temporal memory, ambiguity resolution | Fused observations outperform any single channel on a benchmark suite |
| V601–V650 | Continual learning | Online adapters, replay buffers, drift detection, plasticity budgets, consolidation windows, rollback of learned state, frozen core + mutable edge | Learns new routines without catastrophic regression on holdout tasks |
| V651–V700 | Multi-agent / committee architecture | Planner, executor, verifier, compressor, memory curator, disagreement protocol, evidence arbitration, role isolation | Multi-role architecture improves reliability enough to justify overhead |
| V701–V750 | Distributed and device-aware runtime | CPU/GPU/NPU routing, local/remote split, cache tiers, bandwidth-aware execution, checkpoint migration, low-RAM mode, battery/thermal budgets | Same task graph adapts across constrained and powerful hardware |
| V751–V800 | Formalized safety and invariants | State invariants, typed effects, permission proofs, model checking for small controllers, property tests, forbidden-transition tests, fail-closed modes | Critical controllers have machine-checkable invariants and rollback proofs |
| V801–V850 | Knowledge substrate | Structured concept graph, executable knowledge fragments, compressed indexes, causal links, contradiction sets, source confidence, knowledge aging | Knowledge is compact, queryable, provenance-aware, and updateable |
| V851–V900 | Cognitive architecture integration | Working memory, attention/routing, global task state, planner-memory-perception loop, curiosity under budget, goal arbitration, sleep/consolidation cycle | Components operate as one measured closed-loop architecture |
| V901–V950 | Generalization and transfer | Cross-app transfer, zero/few-shot skill adaptation, abstraction discovery, analogy retrieval, synthetic curricula, benchmark families, unseen-app trials | Skills transfer to unseen but related environments with bounded adaptation |
| V951–V1000 | Hardening and long-horizon autonomy | Long-duration soak tests, fault injection, upgrade compatibility, reproducibility packs, disaster recovery, stable APIs, resource caps, governance files, V1000 audit | Weeks-scale operation with auditable changes, bounded resource use, and reliable rollback |

## Detailed milestone spine

| Version | Suggested focus |
|---|---|
| V66 | EvidenceManifest schema + validator + negative tests |
| V70 | Deterministic replay from captured observations/actions |
| V75 | Failure injection harness: corrupt digest, stale telemetry, missing provenance, partial writes |
| V80 | CI matrix across Python/runtime variants and core modules |
| V85 | Dependency lock, SBOM, license/provenance checks |
| V90 | Android E2E smoke test with synthetic or instrumented device state |
| V95 | Automated rollback rehearsal and recovery-time measurement |
| V100 | Foundation checkpoint: freeze interfaces and publish baseline metrics |
| V110 | Event memory with dedupe and monotonic IDs |
| V120 | Failure Memory clustering and counterexample retrieval |
| V130 | Semantic memory with provenance and contradiction links |
| V140 | Memory decay/retention policy based on measured utility |
| V150 | Memory benchmark and compacted snapshot format |
| V160 | Accessibility + OCR + pixel fusion state estimator |
| V170 | Temporal UI-state graph and transition confidence |
| V180 | Unknown-state detector; refuse low-confidence actions |
| V190 | Visual change localization and region-of-interest scheduling |
| V200 | Perception benchmark across app/state changes |
| V210 | Declarative action model with preconditions/effects |
| V220 | Bounded planner with cost and risk terms |
| V230 | Plan repair from failed actions |
| V240 | Uncertainty-aware branch planning |
| V250 | Planner benchmark and trace visualizer |
| V260 | Android action arbitration and idempotency keys |
| V270 | App/focus/task recovery controller |
| V280 | Long-running watchdog with false-positive controls |
| V290 | Multi-window/device profile abstraction |
| V300 | 24-hour Android soak benchmark |
| V310 | Typed skill manifest |
| V320 | Skill registry and dependency graph |
| V330 | Skill composition and permission envelopes |
| V340 | Skill quality score from reproducible evidence |
| V350 | Skill garbage collection/deprecation |
| V360 | Sparse random projection baseline |
| V370 | KC-style high-dimensional sparse code experiments |
| V380 | Associative recall and approximate matching |
| V390 | Event-driven sparse update path |
| V400 | Sparse-vs-dense benchmark: RAM, latency, recall, robustness |
| V410 | Teacher-trace schema and trace quality filters |
| V420 | Behavior distillation into compact decision tables/rules/adapters |
| V430 | Quantization and codebook experiments |
| V440 | Irreversible compression with task-level distortion metric |
| V450 | Compression frontier report: bytes vs competence vs latency |
| V460 | Calibrated confidence and abstention |
| V470 | Metamorphic tests generated from task invariants |
| V480 | Counterexample generator and regression harvesting |
| V490 | Independent verifier for planned action sequences |
| V500 | Self-evaluation benchmark with precision/recall of failure prediction |
| V510 | Capability-only synthesis request format |
| V520 | Hermetic sandbox runner integration |
| V530 | Generated patch provenance and digest binding |
| V540 | Resource-limited fuzzing of generated components |
| V550 | Synthesis promotion gate with independent verifier |
| V560 | Multimodal observation packet format |
| V570 | Cross-modal alignment and conflict resolution |
| V580 | Temporal multimodal memory |
| V590 | Adaptive sensor scheduling under compute budget |
| V600 | Multimodal benchmark and ablation report |
| V610 | Online learning state separated from frozen release state |
| V620 | Replay/consolidation buffer |
| V630 | Drift detector and learning-rate/plasticity governor |
| V640 | Automatic rollback of harmful learned state |
| V650 | Continual-learning holdout benchmark |
| V660 | Planner/executor/verifier separation |
| V670 | Disagreement and arbitration protocol |
| V680 | Memory curator role with deletion/retention evidence |
| V690 | Parallel hypothesis testing under budget |
| V700 | Committee overhead-vs-reliability benchmark |
| V710 | Hardware capability discovery and task routing |
| V720 | Low-RAM execution profile |
| V730 | Thermal/battery aware scheduling |
| V740 | Local/remote execution split with privacy labels |
| V750 | Cross-device checkpoint migration |
| V760 | Typed side-effect model |
| V770 | Critical state invariants and property tests |
| V780 | Small-controller model checking |
| V790 | Permission proof attached to action plan |
| V800 | Safety invariant audit pack |
| V810 | Compact knowledge graph with source provenance |
| V820 | Causal/temporal relation representation |
| V830 | Contradiction sets instead of destructive overwrite |
| V840 | Knowledge compression and aging |
| V850 | Knowledge substrate benchmark |
| V860 | Working-memory controller |
| V870 | Attention/routing policy under fixed compute |
| V880 | Goal arbitration with explicit priorities and budgets |
| V890 | Consolidation/sleep cycle for memory and learned state |
| V900 | Closed-loop cognitive benchmark |
| V910 | Cross-app abstraction extraction |
| V920 | Few-shot skill adaptation |
| V930 | Analogy retrieval and plan transfer |
| V940 | Synthetic curriculum generator |
| V950 | Unseen-app/generalization suite |
| V960 | Multi-day soak with injected faults |
| V970 | Backward-compatible state/schema migrations |
| V980 | Reproducible release bundle: code, manifests, tests, fixtures, metrics |
| V990 | Disaster recovery from corrupted runtime/memory state |
| V995 | Release-candidate freeze and independent audit |
| V1000 | Audited stable milestone: adaptive, compact, recoverable, evidence-driven FAP |

## Persistent research lanes

These lanes should run in parallel instead of waiting for a single version range: sparse/fly-inspired computation; compact knowledge encoding; Android perception; deterministic replay; continual learning; distillation; resource-aware execution; safety invariants; counterexample generation; and long-horizon failure analysis.

## What V1000 should mean

V1000 should be accepted only if the repository can reproduce a defined benchmark suite from a clean checkout, reconstruct the provenance of promoted skills/models/artifacts, run for long periods while staying inside RAM/CPU/storage budgets, detect and roll back selected regressions, and demonstrate measurable transfer to tasks not directly encoded in the release. If those properties are absent, the project should keep iterating rather than treating the number itself as success.
