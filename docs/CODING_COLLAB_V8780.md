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
RepositoryPlanner
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
python -m unittest   tests.test_fap_repository_structured_patch   tests.test_fap_repository_collab   tests.test_fap_repository_ast_patch   tests.test_fap_repository_agent   tests.test_fap_repository_interaction -v
```

The branch workflow `.github/workflows/coding-collab-expansion.yml` runs the same focused regression lane on pushes to this collaboration branch.

## Continuation contract for another chat

1. Fetch `collab/coding-expansion-v8780` before editing.
2. Keep new work on this branch or a child branch; do not merge to `main` automatically.
3. Prefer structured specs over unconstrained whole-file rewrites when a bounded edit can express the task.
4. Preserve planner SHA preconditions and detached-worktree verification.
5. Add tests with each new coding operation.
6. If the branch diverges from `main`, rebase/merge deliberately and rerun the focused lane before proposing integration.
