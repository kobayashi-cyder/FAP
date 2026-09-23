# FAP Coding Collaboration Branch

Branch: `collab/coding-expansion-v8780`

Purpose: expand repository coding on a non-main line so another ChatGPT/coding-agent session can inspect, extend and test the same work without changing `main`.

## Added capability

### Structured multi-edit provider

`fap_repository_structured_patch.py` adds a provider-neutral edit contract that compiles declarative rows into the existing `FileEdit` pipeline.

Supported operations:

- `python_function_body`: replace one Python function/method body through the existing AST-limited patcher.
- `replace_exact`: deterministic exact-text replacement with an expected match count.
- `create_text`: create an explicitly planned text file.
- `delete_file`: delete an explicitly planned file.

Multiple operations can target the same modified file. They are composed in memory and emitted as one final `FileEdit`, preserving the original plan SHA as the precondition. This removes the previous one-AST-patch-per-file limitation without bypassing sandbox execution or verification.

Example cross-agent rows:

```json
[
  {
    "op": "python_function_body",
    "path": "module.py",
    "target_symbol": "Worker.run",
    "replacement_body": "result = int(value)\nreturn result + 1"
  },
  {
    "op": "replace_exact",
    "path": "README.md",
    "old": "old text",
    "new": "new text",
    "expected_count": 1
  }
]
```

The rows can be parsed with `structured_spec_from_mapping()` and serialized with `structured_spec_to_dict()`.

### Mixed-operation structured planner

`fap_repository_structured_planner.py` adds `RepositoryStructuredPlanner`.

It resolves operations per explicit path instead of applying one broad create/modify/delete flag to every path in the goal. This allows one bounded task to express combinations such as:

```text
Update calc.py and create notes.md
Delete obsolete.md and update calc.py
calc.pyを修正して obsolete.mdを削除
```

The planner keeps the existing `PatchPlan` contract, repository digest, SHA preconditions and `write_enabled=False` boundary. Existing-file create requests and missing modify/delete targets still fail closed.

To use it with the existing coordinator:

```python
from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_structured_planner import RepositoryStructuredPlanner

planner = RepositoryStructuredPlanner(repo_root)
coordinator = RepositoryCodingCoordinator(repo_root, planner=planner)
```

### Automatic verification selector

`fap_repository_test_selector.py` adds `RepositoryVerificationSelector`.

It derives bounded `VerificationCommand` argv vectors from the current `PatchPlan` instead of requiring every caller to hand-build a test list. For Python changes it maps files such as `calc.py` to focused tests such as `tests/test_calc.py`, then adds bounded `unittest discover` regression coverage when required by the plan. If required tests are unavailable, it emits warnings and leaves the command set incomplete so the existing verifier still fails closed.

This means a coding host can now perform:

```text
goal
  -> structured plan
  -> structured edits
  -> automatic focused/regression test selection
  -> detached-worktree verification
```

### Dependency-aware impact analysis

`fap_repository_impact.py` adds `RepositoryImpactAnalyzer`.

The repository index already records Python import edges. The impact analyzer walks those edges in reverse with explicit depth/count bounds, so changing a low-level file can discover indirect dependents and tests without importing or executing project code. For example:

```text
core.py
  <- service.py
      <- tests/test_service.py
```

A change to `core.py` can therefore select `tests/test_service.py` even though the test filename does not match `core.py`.

### Integrated structured coding agent

`fap_repository_structured_agent.py` adds `RepositoryStructuredCodingAgent`.

It combines the collaboration branch components into one non-promoting pipeline:

```text
goal
  -> RepositoryStructuredPlanner
  -> RepositoryImpactAnalyzer / RepositoryVerificationSelector
  -> RepositoryStructuredProposalProvider
  -> detached-worktree execution
  -> focused + regression verification
  -> optional bounded structured repair
  -> verified candidate
```

The agent has no automatic promotion method. A verified result stays outside the source working tree and outside `main` until an explicit existing promotion path is used.

### Cross-chat handoff snapshot

`fap_repository_collab.py` adds `RepositoryCodingCollaboration.snapshot()`.

It returns a content-free handoff record containing:

- collaboration branch
- optional base commit
- plan id
- repository digest
- planned paths and operations
- file precondition hashes
- selected symbols
- required checks
- risk flags

It deliberately excludes source excerpts, generated code and provider messages. The collaboration snapshot rejects `main` and `master` as handoff branches.

## Existing safety path remains unchanged

The expanded provider still feeds the existing architecture:

```text
RepositoryStructuredPlanner (optional)
    -> structured proposal provider
    -> FileEdit
    -> detached Git worktree
    -> RepositoryVerifier
    -> bounded repair
    -> verified candidate
```

No automatic promotion to `main` is introduced.

## Verification

Run:

```bash
python -m unittest \
  tests.test_fap_repository_structured_patch \
  tests.test_fap_repository_structured_planner \
  tests.test_fap_repository_collab \
  tests.test_fap_repository_ast_patch \
  tests.test_fap_repository_planner \
  tests.test_fap_repository_agent \
  tests.test_fap_repository_interaction -v
```

The branch workflow `.github/workflows/coding-collab-expansion.yml` runs the same focused regression lane on Python 3.11 and 3.12 for pushes to this collaboration branch.

## Continuation contract for another chat

1. Fetch `collab/coding-expansion-v8780` before editing.
2. Keep new work on this branch or a child branch; do not merge to `main` automatically.
3. Prefer structured specs over unconstrained whole-file rewrites when a bounded edit can express the task.
4. Use `RepositoryStructuredPlanner` when a single request mixes create/modify/delete targets.
5. Use `RepositoryImpactAnalyzer` / `RepositoryVerificationSelector` to cover indirect dependents and bounded Python tests.
6. Use `RepositoryStructuredCodingAgent` when one host should execute the full non-promoting plan → edit → verify → repair cycle.
7. Preserve planner SHA preconditions and detached-worktree verification.
8. Add tests with each new coding operation.
9. If the branch diverges from `main`, rebase/merge deliberately and rerun the focused lane before proposing integration.
