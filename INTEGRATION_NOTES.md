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
