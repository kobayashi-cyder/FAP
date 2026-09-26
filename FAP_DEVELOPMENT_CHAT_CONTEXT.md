# FAP Development Chat Context — 2026-09-18

This file preserves the project-relevant decisions from the current ChatGPT development session so future work can continue from `main` without depending on chat history.

It intentionally excludes unrelated personal conversation and secrets. It is a development handoff, not a verbatim transcript.

## Project direction

FAP is being developed toward Sol-class practical capability through measured capability growth, not by claiming to be GPT-5.6 Sol.

Core constraints and design choices:

- Keep RAM practical for a 16 GB machine.
- Prefer sparse representations, specialist Skills, selective activation, verification, and modular composition over one large always-resident monolithic model.
- Preserve the separation between FAP Local, FAP-, Student, Knowledge, Teacher, and Skill layers.
- External models may be used as Teacher/evaluator/bootstrap sources, but verified capability should move into FAP where practical.
- Unverified Teacher output must not be written directly into factual Knowledge.
- Continual learning must use `ephemeral -> shadow -> consolidated`, not one-success permanent learning.
- Unknown generated code must never be blindly imported or activated.
- Benchmark answer hard-coding, test weakening, fake implementations, fake benchmark claims, and hidden regressions are forbidden.
- Every capability improvement should be measured for correctness, regression risk, RAM, disk, latency, and evidence quality.

## GitHub operating contract

Repository: `kobayashi-cyder/FAP`

Development policy established in this session:

1. Keep historical mainline work intact.
2. Add cumulative verified snapshots under `releases/vXX/`.
3. Update `FAP_LATEST.md` when a release becomes the current verified snapshot.
4. Never force-push over unrelated updates. If `main` moves, rebuild the new release on top of the new `main`.
5. The main-update listener prepares `listener/vXX` branches from new `main` commits.
6. Merge to `main` only after tests and mechanism validation pass.
7. A push to `main` also triggers the Android APK build workflow.

## Autonomous Capability Loop target

The intended closed loop is:

```text
benchmark / actual task
  -> failure detection
  -> failure clustering
  -> capability-gap estimation
  -> priority selection
  -> Skill Factory request / candidate
  -> static safety gate
  -> unit tests
  -> sandbox execution
  -> development benchmark
  -> untouched holdout benchmark
  -> resource / regression gates
  -> ephemeral
  -> shadow
  -> repeated verified success
  -> consolidated
  -> verified registry
  -> controlled activation
  -> production telemetry
  -> canary/A-B evaluation
  -> keep / expand / rollback / demote / quarantine
  -> Failure Memory
  -> next improvement cycle
```

## Failure taxonomy

Capability-gap analysis should continue to distinguish at least:

- `KNOWLEDGE_GAP`
- `SEMANTIC_GAP`
- `REASONING_GAP`
- `LONG_HORIZON_GAP`
- `MATH_GAP`
- `CODE_GAP`
- `VISION_GAP`
- `IMAGE_GENERATION_GAP`
- `WEB_DESIGN_GAP`
- `TOOL_USE_GAP`
- `MEMORY_GAP`
- `VERIFICATION_GAP`
- `LANGUAGE_GENERATION_GAP`
- `PLANNING_GAP`
- `UNKNOWN_GAP`

Prefer hierarchical causes such as `MATH_GAP -> word_problem -> quantity_relation -> multi_step` rather than one flat label.

Capability priority should broadly favor expected verified gain divided by implementation/resource/regression cost. Frequent, generalizable failures should rank above benchmark-specific tricks.

## V61 — Operational Capability Discovery

V61 connected verified V59 operational outcomes to capability discovery.

Implemented concepts:

- verified-outcome SQLite ledger
- duplicate-safe ingestion
- unverified turn exclusion
- diagnostic/audit separation
- Failure Cluster aggregation
- Evidence Gate to prevent overreaction to a tiny sample
- Capability Priority Engine
- existing-skill reuse resolver
- non-executable Skill Factory request generation
- atomic request queue
- operational capability matrix

Important behavior: if failures repeatedly occurred while an existing Skill such as `math` was already selected, prefer `extend_existing_skill` over creating a duplicate `math` Skill.

## V62 — Verified Candidate Promotion Loop

V62 added the candidate evaluation and promotion side.

Key mechanisms:

- candidate static safety inspection
- unit tests
- subprocess execution
- development benchmark
- sealed untouched holdout
- holdout SHA-256 integrity check before/after evaluation
- measured subprocess peak RSS where available
- resource gate
- regression gate
- persistent PromotionLedger
- `trial_id` replay protection
- content-based evidence-key deduplication
- candidate digest lifecycle separation
- `ephemeral -> shadow -> consolidated`
- verified registry manifest

Critical anti-gaming rule: changing only `trial_id` must not allow the same candidate and same holdout evidence to count multiple times toward consolidation.

V62 validation recorded on main: 42/42 tests PASS and compileall PASS.

## V63 — Verified Activation + Automatic Rollback

V63 added safe post-consolidation activation control.

Main mechanisms:

- Skill Factory output manifest validation
- path-escape rejection
- evaluator-owned holdout requirement
- candidate-tree holdout rejection
- shell and `python -c` rejection
- candidate-tree symlink rejection
- immutable-by-digest managed snapshots
- copy-time digest verification
- atomic `active.json` pointer switching
- verified runtime observation monitoring
- duplicate observation rejection
- minimum evidence before rollback
- quality / success-rate / p95-latency regression detection
- automatic rollback to previous verified digest
- rollback-target digest re-verification
- tamper-evident provenance hash chain

Activation remains a control-plane pointer switch. Unknown candidate code is not directly imported into the FAP process.

V63 validation recorded on main: 63/63 tests PASS, compileall PASS, ResourceWarning-as-error PASS.

## V64 — Verified Runtime Dispatch + Canary A/B

V64 is the current completed release at the time this context was written.

It adds:

- runtime load-time active-slot SHA-256 verification
- deterministic request routing for canary use
- trusted sandbox-runner bridge contract
- baseline/active A-B observation handling
- verified-observation-only comparison
- rollback on sustained quality/success/latency regression
- demotion event after successful rollback
- Failure Memory feedback for demoted candidates
- sanitized Android active-state export without exposing local slot paths

The V64 increment passed 19/19 delta tests, compileall, and warnings-as-errors checks. V63's 63-test baseline was retained as the inherited safety baseline.

A synthetic mechanism demo intentionally forced a worse active candidate and verified:

- baseline success rate: 1.0
- active success rate: 0.5
- quality delta: -0.32
- p95 latency ratio: 2.4x
- rollback triggered
- previous verified version restored
- demotion written only after successful rollback
- Failure Memory updated

These are mechanism-validation fixtures, not claims about real FAP benchmark performance.

## Current main snapshot

At the point immediately before this context commit, `main` was:

`bebc7c7ddde33eb372c12d1e8266846fab8231a6`

Commit message:

`Add V64 verified runtime dispatch and canary A/B loop`

`FAP_LATEST.md` identified V64 as the latest development snapshot.

## Next target — V65

Continue immediately with V65. The next concrete work items are:

1. Connect the real Skill Factory request inbox to candidate outbox processing.
2. Add a trusted sandbox runner implementation boundary instead of only a bridge contract.
3. Ingest real FAP runtime telemetry into the verified A/B monitor.
4. Implement staged canary progression:
   - 5%
   - 20%
   - 50%
   - 100%
5. Require sufficient verified evidence at each stage before promotion.
6. Automatically halt progression on statistically or operationally meaningful regression.
7. Roll back bad candidates through the V63/V64 rollback path.
8. Track repeated rollback/demotion history.
9. Quarantine candidates or candidate families that repeatedly regress.
10. Feed quarantine/demotion causes into Failure Memory and the next capability-improvement cycle.
11. Keep Android active-state synchronization consistent with the current verified runtime state.
12. Preserve all previous safety gates and tests; V65 is cumulative, not a replacement that deletes earlier protection.

## V65 acceptance direction

V65 should not be considered complete merely because code exists. It should include:

- implementation
- unit tests
- regression tests
- integration/mechanism test
- evidence deduplication
- canary-stage transition tests
- rollback tests
- quarantine tests
- malformed telemetry rejection
- unverified telemetry exclusion
- resource measurement where execution is involved
- release report
- updated `FAP_LATEST.md`

If synthetic data is used, label it explicitly as mechanism validation. Do not convert it into a claim about public benchmark performance or Sol parity.

## Continuation instruction

The user explicitly authorized continued forward development without stopping for routine confirmation. Prefer making the next verified improvement, testing it, and pushing it to GitHub. Ask only when a genuinely non-resolvable product decision or missing external credential blocks implementation.
