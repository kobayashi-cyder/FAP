# Public FAP 1.0.01 clean integration

This tree is the contamination boundary for the public 1.x line.

## Included

- public-safe generic modules retained from the 1.0.0-r001 baseline;
- dynamic sparse router and InteractionFabric integration;
- version-neutral local speech runtime;
- browser self-improvement controller with bounded worktree verification;
- native C/C++ deterministic core;
- Android adapter under `android/` with the legacy package/path name removed.

## Explicitly excluded

- versioned V2+ files, release directories, tests, launchers and workflows;
- the prior `fap_v1_0_01_dynamic_sparse_routing_gateway.py`, because it directly inherited the retired V87 gateway chain;
- old `LATEST`, `INTEGRATION_NOTES` and development-chat routing documents that could redirect work into retired lines.

## Promotion gate

`python tools/check_1x_tree.py` must pass. Canonical CI compiles and tests the imported 1.x components.

Component success is not evidence of GPT-5.6 Sol-class general intelligence. Any such comparison requires independent unseen holdouts and measured task-level results.
