# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r003**

This directory is a separate native implementation of the public FAP 1.x behavior.
It does **not** replace the Python mainline. The source branch is
\`side/1.0.01-cpp-native-20260926\`.

## Native scope

The native line moves deterministic, low-level FAP behavior into a
dependency-free C++20 library:

- public r001 adaptive reasoning budget;
- sparse-to-dense extra-path trigger;
- declarative semantic resource/action routing from \`knowledge/*.jsonl\`;
- persistent goal / constraint / explicit-fact state;
- multi-intent planning;
- answer/artifact coverage critic;
- compact lexical semantic memory with Japanese UTF-8 bigram features;
- adaptive response-series redundancy with **6–64 lanes**;
- synthesis committee scaling with **2–8 lanes** and quorum;
- partial salient coverage targets of **55–90%**, rather than forced exhaustive padding;
- stable C ABI for Android/JNI, Rust, C, WebAssembly, or other FFI callers;
- responsive browser UI with C++ WebAssembly native tracing;
- CLI and native regression tests.

Response redundancy is domain-neutral. The lane palette spans direct response,
decomposition, assumptions, mechanism, evidence, counterexample, constraints,
edge cases, alternatives, procedure, analogy, uncertainty, user intent,
compression, verification, and synthesis probing. Roles are reused with
independent variants as the active lane count grows.

The runtime remains sparse for easy turns. Uncertainty, low confidence,
disagreement, counterexamples, structural breadth, route pressure,
verification depth and retries expand the response series. The planner can
reach 64 active lanes without requiring every possible subtopic to be answered.

## Native build

\`\`\`bash
cmake -S native_cpp -B build/native_cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build/native_cpp --parallel
ctest --test-dir build/native_cpp --output-on-failure
\`\`\`

## Browser UI

The UI lives in \`native_cpp/ui\` and displays native route/compute state plus
response lane count, synthesis width and target coverage. Native-only mode
remains available when the conversation backend is offline.

## Compatibility boundary

C++20 is the preferred home for deterministic hot-path logic. Components that
depend on Python runtime semantics, Python AST mutation, the existing
repository-edit sandbox, media/image implementations, network/research
connectors, or platform-specific Android UI glue remain compatibility
boundaries.

The response-series planner does not claim that 64 lanes are 64 independent
language models. It is a scheduling and redundancy contract that gives
downstream generators, critics and tool endpoints enough independent slots to
scale toward that breadth while keeping output bounded.
