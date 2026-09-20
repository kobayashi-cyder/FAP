# FAP latest development snapshot

Current additive development release: **V83 — Bidirectional Visual IR Cognition**.

Source, tests and integration notes are stored under [`releases/v83/`](releases/v83/).

V83 builds on V82 Sparse Adaptive Circuit Orchestrator and adds a shared visual state space instead of making FAP draw directly from natural language.

V83 adds:
- natural language -> `VisualIR` planning for bounded shape/color/position/size facts;
- `RendererPort` with a dependency-free small raster renderer;
- `VisionPort` and `CallableVisionAdapter` so existing Vision output is normalized back into `VisualIR`;
- mandatory render -> Vision -> structured diff verification for every initial and repaired candidate;
- field-level differences for shape, color, position, radius and size;
- local primitive-only repair, preserving unaffected primitives;
- `MotionPrimitive` plus `VisualIR.sample(t)` for video/state transitions;
- optional replaceable renderer/diffusion boundary rather than a diffusion dependency;
- Visual Skill Graph: `imagine -> draw -> see -> review -> repair -> draw`, plus `motion -> draw`;
- verifier-first registration of the verified Visual Skill Graph as the V82 `visual_cognition` sparse specialist.

Combined visual direction:

```text
natural language
      ↓
    VisualIR
      ↓
small/replaceable renderer
      ↓
 existing Vision
      ↓
  VisualIR observation
      ↓
structured local diff
      ↓
local repair only
      └──────────────→ rerender → Vision

MotionPrimitive + time → VisualIR state → same loop
```

**Execution boundary:** `PrimitiveVision` is only the deterministic bootstrap verifier. Production Vision is injected through `CallableVisionAdapter`; external diffusion remains optional.
