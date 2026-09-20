# FAP latest development snapshot

Current additive development release: **V85 — Production Vision Wiring**.

Source, tests and integration notes are stored under [`releases/v85/`](releases/v85/).

V85 builds on V84 Self-Generated Curriculum and V83 Bidirectional Visual IR Cognition. It converts V83's production Vision boundary from a documented injection point into an explicit host runtime.

V85 adds:
- `ProductionVisualRuntime` requiring a real host/existing Vision callback;
- mandatory wrapping through V83 `CallableVisionAdapter`;
- explicit mapper support when the existing Vision does not already return `VisualIR`;
- fail-closed startup when production Vision is missing;
- no silent `PrimitiveVision` fallback in production mode;
- reuse of the same external Vision callback after every local repair/rerender;
- a production manifest that records the external Vision requirement and shared `VisualIR` state.

Production path:

```text
existing / host Vision
        ↓
CallableVisionAdapter
        ↓
VisualIR observation
        ↓
V83 VisualCognitiveLoop
        ↓
structured diff → local repair → rerender → same Vision
```

**Boundary:** the repository still does not contain a specific external computer-vision model. V85 wires the production host contract without pretending that the V83 bootstrap `PrimitiveVision` is a production backend.
