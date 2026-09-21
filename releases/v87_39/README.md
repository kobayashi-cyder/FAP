# FAP V87.39 — Native Geometry + Sparse LBS

V87.39 extends the V87.38 native raster boundary upward into geometry
preparation and deformation.

Moved to a second portable C99 core:
- camera yaw/pitch transform and perspective projection;
- smooth vertex-normal accumulation;
- active 32x32 tile discovery;
- cat coat/face pattern evaluation;
- linear blend skinning;
- sparse LBS updates that only recompute vertices influenced by bones whose
  skin matrices changed.

The rendering path is now:

```text
SparseRouter
  -> Scene/Morphology/DNA semantics (Python)
  -> native geometry preparation (C99)
  -> native raster/shading/FXAA/filmic (V87.38 C99)
  -> PNG/verification (Python)
```

Human LBS keeps previous deformed positions for a persistent mesh. On a pose
change, bone skin matrices are compared; vertices with no influence from any
changed matrix are copied from the previous result instead of recomputed.

Windows build:

```text
BUILD_FAP_V87_39_NATIVE_GEOMETRY.cmd
```

The latest launcher attempts to build V87.38 raster and V87.39 geometry DLLs
when absent. Both retain Python fallback behavior.

Qwen is not used.
