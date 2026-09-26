# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r007**

This is the separate native-oriented FAP 1.x line on
`side/1.0.01-cpp-native-20260926`. It does not replace public main.

## Response-series execution

The runtime keeps easy turns sparse and can expand difficult turns to **128
response lanes** with a **16-lane synthesis committee**. Planned lanes cast
role-sensitive votes; the capacity is an execution/evaluation scale, not a
claim that 128 independent LLMs are running.

The current read-only specialist portfolio contains 11 paths:

- deterministic factual QA;
- verified arithmetic;
- reflective local explanation;
- causal framing;
- semantic rule reasoning;
- code planning;
- verified single-variable linear-equation solving;
- verified free-response SI physics formulas;
- Python AST/static-policy analysis without execution;
- same-key numeric contradiction detection across recent context;
- verified symbolic derivation.

Requirement coverage and multi-segment coverage are audited independently.
High-pressure requests can build a deterministic complementary synthesis from
non-overlapping safe candidates. A verified specialist may replace a weak
primary response when the lane vote and synthesis quorum support it.

Side-effecting artifact generation, repository writes, network actions and
external tool calls are never redundantly replayed.

## Native scope

The C++20 core provides adaptive compute budgeting, 128-lane response planning,
extra-path triggering, semantic routing, persistent goal state, multi-intent
planning, bounded semantic memory, C ABI, WebAssembly UI tracing, CLI and
regression tests. Compatibility specialists are progressively migrated from
Python as native equivalents become worthwhile.

## Build

```bash
cmake -S native_cpp -B build/native_cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build/native_cpp --parallel
ctest --test-dir build/native_cpp --output-on-failure
```
