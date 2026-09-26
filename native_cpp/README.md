# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r004**

This directory is a separate native implementation of the public FAP 1.x behavior.
It does **not** replace the Python mainline. The source branch is
\`side/1.0.01-cpp-native-20260926\`.

## Response-series execution

The r004 bridge makes the r003 6–64 lane response plan affect the answer
selection rather than only exposing capacity metadata.

Each planned lane now casts an actual role-sensitive vote across available
response candidates. The lane palette covers direct answer quality,
decomposition, assumptions, mechanism, evidence, counterexamples, constraints,
edge cases, alternatives, procedure, analogy, uncertainty, user intent,
compression, verification and synthesis.

Candidate generation is deliberately restricted to read-only local specialists:

- deterministic factual QA;
- reflective local explanation;
- generic semantic rule reasoning;
- verified symbolic derivation;
- the normal primary FAP response.

Side-effecting artifact generation, repository writes, network actions and
external tool calls are **not** redundantly replayed.

A verified specialist can replace a weak primary response when the lane vote
and synthesis quorum support the change. Duplicate answers from independent
sources are merged as consensus instead of padded into the visible response.

The native C++ planner still supplies the fast redundancy budget and WebAssembly
trace. The Python compatibility gateway executes the current specialist
portfolio while the remaining specialist bodies are progressively moved to
native code.

## Native scope

The native line includes adaptive compute budgeting, extra-path triggering,
semantic routing, persistent goal state, multi-intent planning, bounded semantic
memory, response redundancy planning, the C ABI, WebAssembly UI tracing, CLI
and regression tests.

The response-series capacity remains **6–64 planned lanes**, with a **2–8 lane
synthesis committee** and **55–90% partial salient coverage target**. The
capacity number is a scheduling/evaluation scale, not a claim that 64
independent language models are running.

## Build

\`\`\`bash
cmake -S native_cpp -B build/native_cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build/native_cpp --parallel
ctest --test-dir build/native_cpp --output-on-failure
\`\`\`
