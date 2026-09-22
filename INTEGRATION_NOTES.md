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

Status: CANDIDATE on `feature/v87-69-verified-candidate-branch`.

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
