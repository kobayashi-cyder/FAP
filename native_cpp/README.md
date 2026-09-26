# FAP C/C++ Native Variant

Version: **1.0.01-cpp-native-r002**

This directory is a separate native implementation of the public FAP 1.x behavior.
It does **not** replace the Python mainline. The source branch is
`side/1.0.01-cpp-native-20260926`.

## Native scope

The native line moves deterministic, low-level FAP behavior into a
dependency-free C++20 library:

- public r001 adaptive reasoning budget;
- sparse-to-dense extra-path trigger;
- declarative semantic resource/action routing from `knowledge/*.jsonl`;
- persistent goal / constraint / explicit-fact state;
- multi-intent planning;
- answer/artifact coverage critic;
- compact lexical semantic memory with Japanese UTF-8 bigram features;
- a native orchestrator combining budget, intent, and route decisions;
- stable C ABI for Android/JNI, Rust, C, WebAssembly, or other FFI callers;
- responsive browser UI with C++ WebAssembly native tracing;
- CLI and native regression tests.

The adaptive budget intentionally mirrors the public Python
`fap_revision_r001.py` thresholds and bounds.

## Native build

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

## Browser UI

The UI lives in `native_cpp/ui`. It combines:

- C++/WASM native route and budget inspection;
- extra-path and multi-intent visualization;
- optional existing `/api/v1/chat` conversation responses;
- responsive desktop/mobile layout;
- Native-only mode when the conversation backend is unavailable.

Build the WASM runtime after activating Emscripten:

```bash
bash native_cpp/ui/build_wasm.sh
python -m http.server 8080 --directory native_cpp/ui
```

Then open `http://127.0.0.1:8080/`.

## Compatibility boundary

C++20 is the preferred home for deterministic hot-path logic. Components that
depend on Python runtime semantics, Python AST mutation, the existing
repository-edit sandbox, media/image implementations, network/research
connectors, or platform-specific Android UI glue remain compatibility
boundaries.

The UI does not duplicate native decision logic in JavaScript. It calls the C
ABI compiled to WebAssembly. The existing conversation API remains optional,
which lets native diagnostics operate even if the Python runtime is offline.

## Normalization note

Python uses Unicode NFKC normalization in some semantic paths. ISO C++ has no
standard NFKC implementation, so this no-dependency build preserves UTF-8 and
performs ASCII case folding plus punctuation compaction. Exact NFKC parity can
be enabled later through an optional ICU adapter without making ICU mandatory.
