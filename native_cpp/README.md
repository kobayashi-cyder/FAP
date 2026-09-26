# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r001**

This directory is a separate native implementation of the public FAP 1.x behavior.
It does **not** replace the Python mainline. The source branch is
`side/1.0.01-cpp-native-20260926`.

## Native scope

The first native revision moves deterministic, low-level FAP behavior into a
dependency-free C++20 library:

- public r001 adaptive reasoning budget;
- sparse-to-dense extra-path trigger;
- declarative semantic resource/action routing from `knowledge/*.jsonl`;
- persistent goal / constraint / explicit-fact state;
- multi-intent planning;
- answer/artifact coverage critic;
- compact lexical semantic memory with Japanese UTF-8 bigram features;
- a small native orchestrator combining budget, intent, and route decisions;
- stable C ABI for Android/JNI, Rust, C, or other FFI callers;
- CLI and native regression tests.

The adaptive budget intentionally mirrors the public Python
`fap_revision_r001.py` thresholds and bounds.

## Build

```bash
cmake -S native_cpp -B build/native_cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build/native_cpp --parallel
ctest --test-dir build/native_cpp --output-on-failure
```

CLI examples:

```bash
./build/native_cpp/fap_native_cli version
./build/native_cpp/fap_native_cli budget 0.8 1
./build/native_cpp/fap_native_cli route . "画像を作って"
./build/native_cpp/fap_native_cli analyze . "今日の天気と時刻を確認"
```

## Compatibility boundary

C++20 is now the preferred home for deterministic hot-path logic. Components
that depend on Python runtime semantics, Python AST mutation, the existing
repository-edit sandbox, media/image implementations, network/research
connectors, or Android UI glue remain outside this first native revision.

Those parts should call the C ABI or C++ library for shared decisions rather
than duplicate the algorithms. This permits gradual replacement without
breaking the existing FAP 1.x public line.

## Normalization note

Python uses Unicode NFKC normalization in some semantic paths. ISO C++ has no
standard NFKC implementation, so this no-dependency build preserves UTF-8 and
performs ASCII case folding plus punctuation compaction. Exact NFKC parity can
be enabled later through an optional ICU adapter without making ICU mandatory.
