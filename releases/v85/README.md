# FAP V85 — Production Vision Wiring

V85 removes the remaining ambiguity between the dependency-free V83 bootstrap Vision and a real host-provided Vision implementation.

## Production path

```text
host / existing Vision callback
        ↓
CallableVisionAdapter
        ↓
VisualIR observation
        ↓
V83 VisualCognitiveLoop
        ↓
structured diff → local repair → rerender → same Vision callback
```

`ProductionVisualRuntime` requires an explicit Vision callback. Missing production Vision is a hard configuration error; it never silently falls back to `PrimitiveVision`.

If an existing Vision already returns `VisualIR`, the callback is used directly. Other output schemas must supply an explicit mapper into `VisualIR`.

This release wires the production boundary. It does not claim that the repository contains a specific external computer-vision model; the host must provide that backend.
