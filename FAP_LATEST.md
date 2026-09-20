# FAP latest development snapshot

Current additive development release: **V85 — Production Vision Host Wiring**.

Source, tests and integration notes are stored under [`releases/v85/`](releases/v85/).

V85 makes the V83 bidirectional visual loop operationally safe for production hosting:
- production Vision must be explicitly configured;
- `PrimitiveVision` is rejected as a production backend;
- existing Vision callbacks are wrapped through `CallableVisionAdapter`;
- bounded detector/object output can be normalized through `ObjectListVisionMapper` into shared `VisualIR`;
- output dimensions and geometry are checked fail-closed;
- bootstrap Vision remains available only through an explicitly named bootstrap builder.

Production route:

```text
existing Vision backend
  -> VisionBackend
  -> ProductionVisionHost
  -> CallableVisionAdapter
  -> VisualIR
  -> V83 review / local repair loop
```

V84 Persistent Self-Generated Curriculum remains the upper-level learning policy underneath this release.

**Execution boundary:** V85 completes the host and adapter path. It does not claim that a separate high-capability Vision model is bundled in this repository; the host application must supply the real Vision callback.
