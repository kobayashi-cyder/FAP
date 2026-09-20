# FAP latest development snapshot

Current additive development release: **V82 — Bidirectional Visual IR Cognition**.

Source, tests and integration notes are stored under [`releases/v82/`](releases/v82/).

V82 is additive on top of V81 Local Adaptive Predictive Core and the current V80/V79 creativity + Primitive Inventor stack. It adds a shared visual intermediate representation and a bounded feedback loop so image generation is always reviewed by Vision before acceptance.

V82 adds:
- natural language -> `VisualIR` planning;
- Visual Primitives for circle/rectangle, RGB color, size and position;
- a dependency-free small raster renderer;
- `VisionPort` plus `CallableVisionAdapter` for injecting the existing Vision implementation;
- mandatory render -> Vision -> structured diff feedback;
- field-level VisualDiff for shape, color, position, radius and size;
- local primitive-only repair and bounded rerender/review;
- `MotionPrimitive` and time-sampled `VisualIR` state transitions for video;
- renderer abstraction so external diffusion remains optional and replaceable;
- Skill Graph integration with active `imagine -> draw -> see -> review -> repair -> draw` and `motion -> draw` paths.

Bootstrap verification covers shape/color/position generation, Vision round-trip, local self-repair, motion transitions and Skill Graph execution.

**Important limitation:** the bundled `PrimitiveVision` is a deterministic bootstrap verifier, not a claim of general visual understanding. Production use should inject the existing Vision through `CallableVisionAdapter`; external diffusion is not required.
