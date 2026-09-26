# FAP V87.38 — Native C99 Raster Core

V87.38 moves the remaining screen-space hot loops from Python into a small
portable C99 shared library.

Native operations:
- triangle barycentric rasterization;
- z-buffer initialization and depth testing;
- interpolated vertex-normal shading;
- V87.32-compatible material response and micro-noise;
- sparse-tile FXAA;
- subject-only filmic finishing.

Python still owns:
- sparse organ routing;
- Scene Graph / Morphology / DNA semantics;
- mesh construction;
- projection;
- active-tile discovery;
- verification and acceptance gates;
- PNG encoding.

This keeps the high-level FAP logic inspectable while moving repeated
per-pixel arithmetic into compiled code.

## Portability

The bridge uses Python stdlib `ctypes`, not a CPython ABI extension.

Build targets:
- Windows: MSVC, GCC or Clang -> `fap_native_raster.dll`;
- Linux: cc/gcc/clang -> `libfap_native_raster.so`;
- macOS: cc/clang -> `libfap_native_raster.dylib`.

On Windows:

```text
BUILD_FAP_V87_38_NATIVE_RASTER.cmd
```

`RUN_FAP_CHAT_LATEST.cmd` also attempts a one-time quiet build when the DLL
is absent. If no compiler is installed, V87.37's Python sparse renderer remains
available as a fail-safe instead of breaking FAP.

## Compatibility

V87.38 does not replace:
- V82 sparse routing;
- V87.37 lazy organs / active tiles;
- V87.36 DNA science verification;
- V87.35 morphology verification;
- V87.34 Scene Graph 2.

Qwen is not used.
