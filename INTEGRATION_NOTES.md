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

Status: CANDIDATE on `feature/v87-66-repository-planner`.

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
