# FAP V81 — Bidirectional Visual IR Cognition

V81 adds a shared visual state space so FAP does not generate images directly from language. The mandatory path is:

```text
natural language
  -> imagine: VisualIR
  -> draw: RendererPort
  -> see: existing Vision / VisionPort
  -> review: structured VisualDiff
  -> repair: local primitive fields only
  -> draw -> see ... until verified or bounded stop
```

## Core rules

- `VisualIR` is the common intermediate representation for imagining, seeing, reviewing and motion state.
- The renderer is intentionally small and dependency-free for bootstrap tests.
- Every generated frame is sent back through `VisionPort`; there is no verified-output shortcut that bypasses Vision.
- `CallableVisionAdapter` is the production boundary for the existing Vision implementation.
- Differences are structured by primitive and field (`kind`, `color`, `position`, `size`, `radius`).
- Repair changes only the affected primitive fields. A shape-kind mismatch replaces only that primitive, not the whole scene.
- Video is represented by `MotionPrimitive` plus time sampling of `VisualIR`; it is a state-transition problem rather than a separate generator.
- External diffusion is optional. `RendererPort`/`CallableRendererAdapter` allows a later renderer replacement without changing the cognitive loop.

## Skill Graph

The verified loop is registered as these active skill nodes:

```text
imagine -> draw -> see -> review -> repair -> draw
motion -------------------------------> draw
```

The graph manifest is `fap.skill-graph.visual.v1` and records:

- shared state space: `VisualIR`
- Vision feedback: required
- external diffusion: not required
- repair scope: local primitive fields

## Bootstrap verification

The first-stage automated tests cover:

1. natural language -> VisualIR -> render -> Vision -> zero diff;
2. shape + color + position mismatch detection and local repair;
3. rectangle size local repair;
4. Motion Primitive state transitions;
5. Skill Graph feedback-cycle integrity;
6. Skill Graph end-to-end verified generation.

Run:

```bash
python -m compileall -q releases/v81/visual_cognition
python -m unittest discover -s releases/v81/visual_cognition/tests -p "test_*.py" -v
```

The bootstrap `PrimitiveVision` exists only for deterministic dependency-free verification. Production integration should inject the existing Vision using `CallableVisionAdapter`.
