# FAP latest development snapshot

Current mainline candidate: **V87.38 — Native C99 Raster Core**.

V87.38 native-compiles the remaining screen-space hot loops while preserving
V87.37 sparse routing and lazy organ loading.

Moved from Python into a portable C99 shared library:
- triangle barycentric rasterization;
- z-buffer initialization and depth testing;
- interpolated normal/material shading;
- deterministic micro-surface noise;
- sparse active-tile FXAA;
- subject-only filmic finishing.

The bridge uses Python stdlib `ctypes`, so it is not tied to a CPython
extension ABI.

Build targets:
- Windows -> `fap_native_raster.dll`;
- Linux -> `libfap_native_raster.so`;
- macOS -> `libfap_native_raster.dylib`.

Windows manual build:

```text
BUILD_FAP_V87_38_NATIVE_RASTER.cmd
```

The normal launcher also attempts a one-time quiet native build when the DLL is
absent. If no supported C compiler is installed, FAP falls back to V87.37's
Python sparse renderer instead of failing.

Still handled in Python:
- V82 sparse organ routing;
- Scene Graph / Morphology / DNA semantics;
- mesh construction;
- camera projection and active-tile discovery;
- artifact verification / acceptance;
- PNG encoding.

Run:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Compatibility:
- V87.37 sparse routing/lazy organs remain;
- V87.36 Scientific DNA remains;
- V87.35 Cat Morphology remains;
- V87.34 Scene Graph 2 remains;
- earlier reasoning/physics/chat-speed paths remain;
- Qwen is not used.
