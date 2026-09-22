# FAP V87.65 Repository Index

Status: PROMOTED TO MAIN on 2026-09-22.

V87.65 is an additive repository-understanding layer. It preserves the existing FAP runtime and adds a read-only repository map for the next repository-scale coding-agent stage.

## Why this exists

The current `fap_code_generator.py` remains a constrained single-artifact generator:
request -> CodeSpec -> candidate -> validation -> bounded repair -> artifact.

The missing first layer for a repository-scale coding agent is repository understanding.

## Added in V87.65

`fap_repository_index.py`

Provides:

- read-only repository scan
- deterministic file map
- Python AST symbol index
- Python import dependency edges
- file hashes and sizes
- bounded per-file parsing
- common vendor/runtime directory exclusions
- no project-code import or execution
- text and JSON CLI output
- adapter-friendly `build_repository_context()`

## Verification

```bash
python -m unittest discover -s tests -v
python fap_repository_index.py /path/to/FAP
python fap_repository_index.py /path/to/FAP --json
```

The bundled V87.65 unit tests passed before promotion.

## Next integration step

Do not wire write access yet.

First connect this read-only context to a new repository-coding planner behind an explicit interface:

1. inspect repository
2. choose relevant files/symbols
3. produce a patch plan
4. apply only inside a sandbox/worktree
5. compile/tests
6. failure analysis
7. bounded repair
8. regression
9. only then promotion decision

The current `fap_code_generator.py` remains unchanged until repository-scale planning and regression tests prove no behavior loss.


# FAP V87.66 Repository Reader + Planner

Status: PROMOTED TO MAIN on 2026-09-22 via PR #87 after Python 3.11/3.12 verification.

V87.66 keeps repository-scale coding read-only. It adds bounded source selection and deterministic patch planning without patch application, subprocess execution, git mutation or direct main writes.

## Added

- `fap_repository_reader.py`
  - task-relevant file/symbol ranking;
  - bounded dependency-neighborhood expansion;
  - repository/file SHA-256 freshness checks;
  - bounded source excerpts;
  - fail-closed stale-source handling;
  - configurable file/byte budgets.

- `fap_repository_planner.py`
  - deterministic `fap.repository.plan.v1` output;
  - per-file `before_sha256` preconditions;
  - inspect/modify/create/delete intent classification;
  - required verification checks and risk flags;
  - stable `plan_id`;
  - `write_enabled=false` invariant.

- V87.65 index hardening
  - large files are size-checked before source parsing and hashed incrementally;
  - `from pkg import util` now exposes both package and member-module dependency edges;
  - relative imports are normalized for dependency analysis.

## Explicit boundary

V87.66 does **not** contain a patch executor.

The next stage may add a sandbox/worktree executor, but it must consume V87.66 plans and enforce:

1. repository digest/freshness validation;
2. per-file `before_sha256` validation;
3. sandbox/worktree-only writes;
4. compile/static checks;
5. focused tests;
6. bounded repair;
7. regression tests;
8. explicit promotion decision.

The existing `fap_code_generator.py` remains unchanged.


# FAP V87.67 Worktree Patch Executor

Status: PROMOTED TO MAIN on 2026-09-22 via PR #89 after Python 3.11/3.12 verification.

V87.67 introduces the first repository write capability, but only inside a detached temporary Git worktree. The source working tree and main branch are never edited by the executor.

## Added

- `fap_repository_executor.py`
  - consumes `fap.repository.plan.v1`;
  - rejects stale repository digests and stale per-file SHA-256 values;
  - creates a detached temporary worktree from the current HEAD;
  - allows only planned create/modify/delete operations;
  - rejects absolute paths, traversal, `.git`, symlink path components and unplanned files;
  - applies bounded UTF-8 edits only inside the worktree;
  - exposes created files through intent-to-add so they are included in diff validation;
  - runs `git diff --check`;
  - returns a bounded structured diff/report;
  - always removes one-shot worktrees.

## Explicit boundary

V87.67 does not run project tests, repair failing patches, commit candidate changes, create branches, push, merge, or promote anything.

The next stage is V87.68: verification and bounded repair over an open V87.67 sandbox session.


# FAP V87.68 Verification + Bounded Repair

Status: PROMOTED TO MAIN on 2026-09-22 via PR #90 after Python 3.11/3.12 verification.

V87.68 separates candidate verification from patch application and adds a bounded retry controller.

## Added

- `fap_repository_verifier.py`
  - internal Python `compile()` syntax validation without importing project modules;
  - explicit focused/regression argv commands with `shell=False`;
  - executable allowlist, command count limit, timeout limit and output cap;
  - minimal verification environment without inherited token/secret variables by default;
  - source working-tree status/digest checks before and after verification;
  - rejection of unexpected modified or untracked sandbox files;
  - deterministic verification states ending in `verified_candidate`.

- `BoundedRepairLoop`
  - each retry starts from a fresh detached V87.67 worktree;
  - failing execution/verification evidence is passed to an external repair proposal provider;
  - repair count is hard-bounded (default 2, maximum 4);
  - no candidate is committed or promoted automatically.

## Verification state

`applied_in_sandbox -> static_pass -> focused_test_pass -> regression_pass -> verified_candidate`

Any missing required check, syntax failure, required command failure, timeout, output overflow, sandbox contamination or source-tree mutation rejects the candidate.

## Explicit boundary

V87.68 still has no branch creation, commit, push, PR, merge or main-promotion capability. V87.69 may consume only `verified_candidate` evidence for an explicit promotion gate.


# FAP V87.69 Verified Candidate Branch Gate

Status: PROMOTED TO MAIN on 2026-09-22 via PR #91 after Python 3.11/3.12 verification.

V87.69 adds an explicit promotion gate from a freshly re-verified sandbox candidate to a local Git candidate branch.

## Added

- `fap_repository_promotion.py`
  - requires matching `plan_id`, expected base commit, explicit branch approval and a non-empty reason;
  - re-applies and re-verifies the candidate in a fresh V87.67 worktree;
  - creates Git blobs/tree/commit with plumbing commands instead of checking out or modifying the source tree;
  - creates only a deterministic `fap/candidate/<plan-id-prefix>` local branch;
  - fails closed on branch collision;
  - verifies source HEAD and working-tree status remain unchanged;
  - rollback removes a candidate ref only when this invocation created it and it still points to the exact candidate commit.

## Explicit boundary

V87.69 does not push, open a remote PR, merge, fast-forward main, delete branches, or alter the currently checked-out source branch.

A candidate branch is evidence-bearing output for an external/human promotion decision, not permission to merge.


# FAP V87.70 Repository Coding Coordinator

Status: PROMOTED TO MAIN on 2026-09-22 via PR #92 after Python 3.11/3.12 verification.

V87.70 composes the repository-coding stack behind one bounded orchestration API without changing the existing single-artifact `fap_code_generator.py`.

## Added

- `fap_repository_agent.py`
  - read + plan + proposal-provider + sandbox apply + verification + bounded repair;
  - returns a structured `fap.repository.coding.v1` result;
  - tracks the final repaired edit set;
  - catches proposal-provider and pipeline failures into fail-closed rejected results;
  - never promotes automatically;
  - exposes a separate `promote_verified()` method that reuses the V87.69 explicit approval gate.

## Provider boundary

The proposal provider receives only the structured plan and bounded read context and returns declarative `FileEdit` values. FAP core does not require a particular model or provider and does not assume Qwen or any network service.

## End-to-end flow

`goal -> read -> plan -> proposal -> worktree -> static -> focused tests -> regression -> bounded repair -> verified candidate`

Promotion remains separate:

`verified candidate + explicit PromotionApproval -> fresh re-verification -> local fap/candidate branch`


# FAP V87.71 FCA Repository Evidence Capsule

Status: PROMOTED TO MAIN on 2026-09-22 via PR #93 after Python 3.11/3.12 verification.

V87.71 exports verified repository-coding evidence through the existing `fca-fap.exchange.v1` schema without exporting executable code or edit payloads.

## Added

- `fap_fca_repository_exchange.py`
  - exports only `verified_candidate` repository-coding results;
  - records exact FAP source commit, plan ID, repository digest and per-file before/after hashes;
  - records bounded verification facts and optional successful candidate-branch provenance;
  - hashes the user goal rather than exporting the goal text;
  - forbids source content, replacement text, excerpts, diffs, argv and command output;
  - seals the capsule with canonical SHA-256;
  - validates the capsule before emission.

## Cross-project boundary

The capsule is provenance only. It does not authorize FCA to execute code, bypass connectome selection, promote a branch, push, open a PR, merge, or update main.

FCA must independently receive and evidence-gate the capsule before any adaptation.


# FAP V87.72 Repository Coding Host Runner

Status: CANDIDATE on `feature/v87-72-repository-host-runner`.

V87.72 exposes the V87.70 repository-coding coordinator as a provider-neutral callable host boundary without importing FCA or granting promotion authority.

## Added

- `fap_repository_host.py`
  - accepts a trusted host proposal provider, verification commands and optional bounded repair provider;
  - runs the existing read/plan/worktree/verify/repair stack;
  - returns only `fap.repository.host.v1` typed summary metadata;
  - exports plan ID, repository digest, bounded progress and attempt/repair counts;
  - never exports edit content, source excerpts, diffs or raw verification output;
  - strips arbitrary provider exception message text from rejection reasons;
  - does not create candidate branches or call the V87.69 promotion gate.

## Host-composition boundary

FAP does not import FCA and FCA does not import FAP.

A host application may inject this callable into FCA's `RepositoryCodingHostBinding`. FCA remains responsible for connectome-first selection and exchange-evidence gating; FAP remains responsible for sandboxed repository coding and verification.

The injected proposal/repair providers are trusted host components. Their declarative edits remain constrained by the V87.66-V87.70 planner/executor/verifier stack.


# FAP V87.73 Exponential-Linear Interaction Fabric

Status: PROMOTED TO MAIN on 2026-09-22 via PR #96 after Python 3.11/3.12 and compatibility verification.

V87.73 keeps FAP standalone while generalizing chat and repository coding behind
one bounded interaction contract.

## Added

- `fap_exponential_linear.py`
  - C1-continuous exponential-to-tangent-linear scale;
  - hard maximum scale;
  - generic structural demand estimator;
  - shared bounded interaction budgets.

- `fap_interaction_fabric.py`
  - dynamic endpoint registration;
  - channel isolation;
  - scored provider-neutral routing;
  - bounded candidate breadth;
  - sanitized probe/handler failure reporting;
  - no topic-specific routing branches.

- `fap_repository_interaction.py`
  - mounts V87.66-V87.72 repository coding as a fabric endpoint;
  - per-request adaptive max-files/source-bytes/repair budgets;
  - source/main remain unchanged because existing worktree verification is reused;
  - scorer is injected rather than hardcoded.

- `fap_v87_73_exponential_linear_gateway.py`
  - existing V87.64 chat remains the mandatory standalone fallback;
  - arbitrary future endpoints can be registered without editing the main route;
  - FCA is optional and not imported.

## Hard limits

Adaptive expansion is bounded at 32 route candidates, 250k context characters,
1MB repository source context, 96 reasoning steps, 4 repair rounds and 120k
output characters.

This release does not weaken the V87.69 explicit promotion gate and does not add
automatic branch merge/main promotion.


# FAP V87.74 Cooperative Interaction Chain

Status: CANDIDATE on `feature/v87-74-cooperative-interaction-chain`.

V87.74 adds optional bounded multi-endpoint handoff above the V87.73 fabric.

## Added

- endpoint allow/exclude filters on `InteractionFabric.dispatch()`;
- `InteractionChainCoordinator`;
- typed `InteractionHandoff`;
- explicit host-provided HandoffPolicy;
- no endpoint revisit by default;
- original exponential-linear reasoning budget constrains maximum chain depth;
- handoff text and history bounds;
- sanitized handoff-policy failures;
- V87.74 gateway API for explicit chain execution.

## Compatibility boundary

Default chat routing remains the V87.73 single-dispatch path. No existing chat
request is automatically converted to multi-step execution.

Repository promotion remains separately gated and no chain step may bypass the
V87.66-V87.72 repository safety stack.
