# Public FAP 1.0.01 clean integration

The active public surface is the 1.x line.

## Isolation rules

- Active entrypoints do not import pre-1.x numbered gateways.
- Legacy versioned paths are excluded from the active tree.
- Capability ports are copied onto the 1.x spine instead of merging divergent
  historical ancestry.
- Unknown local requests fail closed.
- Browser-driven self-improvement produces isolated candidates and cannot
  automatically promote itself to `main`.
- Capability claims remain tied to the evidence level that actually ran.

## Canonical verification

`Public FAP 1.x CI` is the single active workflow. It checks:

1. 1.x path hygiene and release/version consistency;
2. integrated Python runtime behavior;
3. bounded adaptive compute and dynamic-sparse routing;
4. local speech regression tests;
5. self-improvement isolation regressions;
6. native C++ build/tests;
7. Android 1.x adapter compilation.

Real-device speech/Android behavior, authenticated real-browser operation, full
Python/C++ parity, and model-level intelligence remain separate evidence gates.
