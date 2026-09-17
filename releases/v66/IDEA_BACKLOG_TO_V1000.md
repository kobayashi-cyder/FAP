# FAP Experimental Idea Backlog — through V1000

This file is deliberately broader than the roadmap. Items are hypotheses, not commitments. Each should have a baseline, a measurable success criterion, a resource budget, and a kill criterion.

## Evaluation frame

For every experiment record: task success rate, regression rate, RAM peak, persistent storage growth, median/p95 latency, CPU time, energy/thermal cost where measurable, reproducibility, and recovery behavior. Prefer improvements that move several metrics at once rather than winning one benchmark by consuming much more memory or compute.

| Lane | Experiment ideas | Useful signal | Kill criterion |
|---|---|---|---|
| Sparse cognition | KC-like sparse expansion, random projection, WTA routing, sparse associative memory, locality-sensitive codes, SDR-like representations | Better approximate recall or routing at lower RAM/latency | No task benefit after controlled sparsity sweep |
| Fly-inspired routing | Fixed random projection + learned sparse readout; novelty channels; parallel micro-circuits; fast inhibitory competition | Fast classification/routing from small learned state | Dense baseline is equally fast/smaller |
| Structural compression | Graph motifs, reusable subplans, macro-actions, grammar induction, subroutine mining | Fewer stored traces with same replay competence | Compression harms holdout success beyond budget |
| Knowledge coding | Dictionary/codon-like chunk IDs, variable-length concept codes, relation triples, executable concept fragments | Storage reduction and fast lookup | Encoding complexity dominates savings |
| Behavior distillation | Distill successful traces to rules, trees, finite-state controllers, tiny adapters | Small artifact reproduces narrow competence | Distilled form fails under minor variation |
| Neural distillation | Tiny local student, LoRA/adapters, quantized classifier/router, representation matching | Improved generalization under fixed RAM | Requires model size outside target hardware budget |
| Retrieval | Hybrid lexical/vector/graph retrieval, temporal decay, utility-weighted retention, novelty weighting | Higher relevant-memory hit rate | Added index cost exceeds task gain |
| Memory consolidation | Replay during idle periods, merge near-duplicates, summarize episodes, keep counterexamples losslessly | Lower memory growth without forgetting critical failures | Counterexample loss or silent contradiction overwrite |
| Forgetting | TTL, utility decay, LRU by concept family, probabilistic retention, protected memories | Stable storage footprint | Repeated relearning of important knowledge |
| Contradiction handling | Keep competing claims with provenance/confidence instead of overwrite | Better behavior under changing environments | Complexity adds no measurable decision benefit |
| Working memory | Small explicit scratch state, bounded slots, decay, salience routing | Lower context/compute requirement | More planning failures than stateless baseline |
| Planning | A*, beam search, MCTS-lite, HTN, policy cache, plan repair, risk-aware search | Higher task completion per action/time budget | Search overhead exceeds execution savings |
| Reactive control | Behavior trees, finite-state controllers, event-driven rules | Fast recovery from common UI failures | Brittle across small UI changes |
| Meta-controller | Learn when to use rule, planner, retriever, verifier, or external model | Lower average cost for same quality | Routing errors outweigh savings |
| Uncertainty | Confidence calibration, conformal-like thresholds, abstain/retry policy | Fewer high-cost wrong actions | Excessive abstention stalls useful work |
| Self-critique | Independent verifier, invariant checker, counterexample search, duplicate-plan comparison | Catches failures before side effects | Critic strongly correlates with same errors as planner |
| Synthetic tests | Mutate UI trees, timings, texts, ordering, missing nodes, stale observations | Wider regression coverage | Synthetic failures do not correlate with real failures |
| Failure Memory | Cluster failures by mechanism, minimal reproducer extraction, recurrence weighting | Faster repair and fewer repeat failures | Memory becomes noisy and retrieval precision collapses |
| Android perception | Accessibility tree + screenshot ROI + OCR + temporal delta | More stable UI-state recognition | OCR cost too high vs accessibility-only baseline |
| Pseudo-OCR | Glyph/patch hashing, template dictionary, tiny recognizer, local line segmentation | Read repeated app text with very low compute | Poor robustness to font/scale/theme changes |
| UI graph | Learn screen-state nodes and action transitions with confidence | Predictable recovery/navigation | Graph churn too high on dynamic screens |
| Action safety | Idempotency keys, pre/postcondition checks, action leases, rate limits | Fewer duplicate/destructive actions | Latency overhead hurts time-critical tasks |
| Focus recovery | Detect package/window mismatch and selectively relaunch target | Higher long-run task uptime | Relaunch loops create more disruption than benefit |
| Multi-window | Per-display state, display ownership, focus arbitration, independent watchdogs | Stable concurrent app operation | Platform limits make reliability unacceptable |
| Deterministic replay | Record normalized observations, decisions, actions, random seeds | Exact or near-exact regression reproduction | Hidden nondeterminism remains too high |
| Sandbox | Fixed executable, JSON protocol, no shell, cgroups/container limits, network deny by default | Safe testing of generated components | Isolation cannot be independently verified |
| Code synthesis | Generate capability specs first, code second; patch size limits; file allowlists | Useful patches with bounded review surface | Generated patches repeatedly fail evidence gates |
| Auto-repair | Failure -> minimal reproducer -> candidate patches -> sandbox -> holdout -> canary | Reduced human repair work | Repair loop cycles or overfits regressions |
| Continual learning | Frozen core + mutable edge, episodic replay, adapter bank, drift detector | Learns new routines without old-task loss | Catastrophic forgetting above threshold |
| Curriculum | Order tasks from stable primitives to combinations; auto-generate variants | Faster acquisition and transfer | Curriculum overfits known environment |
| Skill composition | Typed inputs/outputs, preconditions/effects, permission envelope | Recombination without bespoke code | Composition failures require too many special cases |
| Skill pruning | Remove low-utility or redundant skills; merge equivalent skills | Smaller registry, lower routing ambiguity | Deletion increases relearning cost |
| Multi-agent | Planner/executor/verifier/curator roles with isolated state | Reliability gain on complex tasks | Compute/latency overhead exceeds gain |
| Debate/committee | Diverse hypotheses, disagreement-triggered verification only | More robust uncertain decisions | Agents collapse to correlated answers |
| Resource routing | Choose algorithm based on RAM/latency/battery/thermal state | Better stability on constrained phones | Routing overhead or misprediction is too costly |
| Low-RAM mode | Memory-mapped indexes, compact structs, streaming parsers, lazy load, bounded caches | Operates within ~16 GB host and much smaller mobile budgets | Performance becomes unusable |
| WASM | Move compact deterministic kernels into WASM; stable ABI; sandbox-friendly modules | Small portable fast primitives | Call/serialization overhead dominates |
| Binary knowledge packs | Immutable content-addressed packs with compact indexes | Easy dedupe, provenance, rollback | Update granularity becomes too coarse |
| Event-driven runtime | Replace polling where possible with observation events and deadlines | Lower CPU/battery use | Missed events reduce reliability |
| Temporal compression | Store deltas/event changes instead of full frames/state | Lower trace size | Reconstruction cost/error too high |
| Provenance | Every learned/derived artifact links to sources, tests, digest, parent artifact | Auditable learning and rollback | Metadata growth becomes excessive without value |
| Reproducibility | Clean-checkout test packs, fixed seeds, fixtures, environment manifest | Independent verification succeeds | Environment coupling prevents reproduction |
| Formal invariants | Forbidden state transitions, typed effects, property tests, small model checking | Prevents classes of failures | Formal model diverges from runtime reality |
| Privacy boundary | Label data local-only/exportable/derived; redact secrets from traces | Safer local autonomy | Policies too coarse to enforce correctly |
| Long-horizon autonomy | Lease-based goals, checkpoints, heartbeat, budget exhaustion behavior | Multi-day tasks recover cleanly | State drift accumulates faster than recovery |
| Sleep/consolidation | Idle-time dedupe, summarization, index rebuild, benchmark replay | Better next-day performance and bounded storage | Background work consumes excessive resources |
| Curiosity | Explore only when expected information gain exceeds cost/risk | Discovers useful UI transitions/skills | Exploration produces low-value churn |
| Transfer | Abstract app-independent patterns: login, reward claim, dismiss modal, recover package | Faster adaptation to unseen apps | Abstractions hide important app-specific constraints |
| Generalization tests | Hold out entire apps, UI themes, timing profiles, text variants | Measures real transfer | Benchmark too synthetic/easy |
| Compression frontier | Plot competence vs bytes vs latency vs energy for each representation | Rational architecture choices | No candidate beats simple baseline |
| Architecture search | Swap memory/router/planner modules behind stable interfaces | Evidence-based evolution | Interface overhead blocks optimization |
| Self-description | Runtime emits machine-readable capability/limit manifest | Better planning and safer delegation | Manifest becomes stale/untrusted |
| Version archaeology | Re-run old releases/tests periodically; detect lost capabilities | Prevents silent historical regression | Maintenance cost exceeds value; then sample releases |
| Anti-overfitting | Hidden holdouts, delayed evaluation, mutation tests, unseen-app tasks | More credible self-improvement | Candidate gains vanish on hidden set |
| Canary policy | 1/5/20/50/100% stages based on risk class rather than fixed schedule | Faster safe promotion | Stage complexity adds no protection |
| Quarantine | Quarantine candidate families and failure mechanisms, not only hashes | Avoid repeated bad idea families | Over-broad quarantine blocks innovation |
| Rollback | State/data/schema-aware rollback, not code-only rollback | Reliable recovery after learned-state changes | Rollback cannot restore consistent state |
| Disaster recovery | Corrupt index, kill process, partial write, disk-full, stale lock scenarios | Measured recovery time and integrity | Recovery remains manual/unbounded |
| Benchmark economics | Score quality per MB, per second, per joule, per stored byte | Keeps project aligned with compact intelligence | Metric gaming; require multi-metric dashboard |

## High-risk / high-reward hypotheses

These deserve isolated branches and strict benchmarks rather than immediate integration.

| Hypothesis | Why it might work | Main risk |
|---|---|---|
| Sparse high-dimensional codes can replace some learned dense embeddings for routing/retrieval | Fast approximate similarity and very small mutable state | Poor semantic generalization |
| A large fraction of useful behavior can be compressed into reusable subplans + exception memory | Real app tasks contain repeated motifs | Edge cases explode and erase compression gains |
| Failure Memory is more valuable than success-memory after a competence threshold | Avoiding known traps improves long-run reliability | Bias toward conservatism and under-exploration |
| A tiny router plus specialized deterministic skills beats one general local model on device automation | Narrow tasks reward specialization | Maintenance and routing complexity |
| Continual improvement can happen mostly by adding/removing skills and memory, not rewriting the core | Stable core limits regression surface | Core bottlenecks may eventually dominate |
| Codon/dictionary-like binary knowledge packs can make learned structure highly compact | Repeated motifs can share identifiers | Encoding becomes opaque and brittle |
| Fly-inspired random sparse projections can provide fast novelty detection and approximate identity | Biological precedent for efficient sparse discrimination | Mapping from text/UI semantics may be weak |
| Repeated self-distillation can shrink behavior while preserving task competence | Narrow task distributions are compressible | Compounding teacher errors and irreversible loss |

## Suggested experiment cadence

Use small release blocks: hypothesis version -> implementation version -> adversarial/negative-test version -> benchmark version -> keep/modify/kill decision. Failed ideas should remain documented with evidence so later versions do not rediscover the same dead end blindly.

## V1000 idea-selection rule

The final architecture should not be the accumulation of all experiments. By V1000, many ideas should have been deleted. Keep only components that survive reproducible holdout tests and justify their complexity in quality, RAM, latency, storage, energy, recoverability, or transfer.
