# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r008**

This remains the separate native-oriented FAP 1.x line on
`side/1.0.01-cpp-native-20260926`; public main is unchanged.

## Effective response redundancy

Easy turns remain sparse. Difficult turns can expand to **128 response lanes**
with a **16-lane synthesis committee**. Lanes do not merely score one answer:
they vote across a growing set of genuinely different read-only candidate paths.

The current portfolio contains **16 specialist/exploration paths**:

- deterministic factual QA;
- verified arithmetic;
- reflective explanation;
- causal framing;
- semantic rule reasoning;
- code planning;
- verified one-variable linear equations;
- verified numerical physics formulas;
- Python AST/static-policy analysis without execution;
- numeric contradiction detection across recent context;
- multi-expression arithmetic exploration;
- syntax-repaired Python candidate generation with reparse verification;
- explicit-edge causal graph path exploration;
- counterexample/falsification-condition generation;
- long-form assignment contradiction detection;
- verified symbolic derivation.

Requirement coverage and multi-segment coverage feed candidate scoring. Under
high pressure, complementary non-overlapping safe candidates can be combined
into a deterministic synthesis candidate before the 128-lane vote finishes.

Side-effecting artifact generation, repository writes, network actions and
external tool calls are never redundantly replayed. The 128-lane figure is an
execution/evaluation capacity, not a claim that 128 independent LLMs exist.

## Native scope

C++20 supplies the fast adaptive budget, 128-lane planner, semantic router,
goal state, multi-intent planning, bounded semantic memory, C ABI, WebAssembly
trace, CLI and native regression tests. Higher-level compatibility specialists
are migrated to native code selectively where doing so improves latency or
determinism.

## Build

```bash
cmake -S native_cpp -B build/native_cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build/native_cpp --parallel
ctest --test-dir build/native_cpp --output-on-failure
```
