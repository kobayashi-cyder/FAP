# FAP V83 — Bidirectional Visual IR Cognition

V83 adds a shared visual state space so FAP does not draw images directly from natural language.

## Mandatory closed loop

```text
natural language
  -> imagine: VisualIR
  -> draw: RendererPort
  -> see: existing Vision through VisionPort
  -> review: structured VisualDifference
  -> repair: affected primitive fields only
  -> draw -> see -> review ... bounded repeat
```

A candidate is never accepted directly from the renderer. The initial render and every locally repaired render are returned through Vision before `verified=True`.

## Shared Visual IR

The same `VisualIR` represents:
- intended scene;
- observed scene normalized from Vision;
- locally repaired scene;
- time-sampled motion state.

Bootstrap Visual Primitives:
- circle;
- rectangle;
- RGB color;
- x/y position;
- width/height/radius.

## Existing Vision integration

`CallableVisionAdapter` wraps an existing Vision callback.

- If Vision already returns `VisualIR`, it is used directly.
- If Vision returns its own object/JSON schema, a mapper normalizes that output into `VisualIR`.

`PrimitiveVision` is only a deterministic bootstrap backend for automated tests; it is not intended as a replacement for the existing Vision system.

## Local review and repair

`VisualDiffer` emits field-level differences:
- `kind`;
- `color`;
- `position`;
- `size`;
- `radius`;
- missing/extra primitive evidence.

`LocalVisualRepairer` patches only the affected primitive/fields. Unaffected primitives are retained unchanged.

## Video / motion

Video is represented as `VisualIR + MotionPrimitive + time`.

The initial Motion Primitive is `translate`; `VisualIR.sample(t)` produces a visual state at time `t`. Additional motion families can be added without creating a separate video state space.

## Renderer replacement

The default `SmallRasterRenderer` has no external dependency.

`RendererPort` and `CallableRendererAdapter` are the replacement boundary for a later renderer or diffusion backend. External diffusion is therefore optional, not required by the cognition loop.

## Skill Graph

The visual subgraph is:

```text
imagine -> draw -> see -> review -> repair -> draw
motion ------------------------------------> draw
```

Manifest:
- schema: `fap.skill-graph.visual.v1`
- shared state: `VisualIR`
- Vision feedback: required
- repair scope: local primitive fields
- external diffusion: not required

After this graph is verified, `VisualAdaptiveCircuitBridge` registers it as the V82 `visual_cognition` specialist. V82 Verifier First grants execution rights; V82 sparse routing then decides when the visual skill runs.

## Automated verification

V83 tests verify:
1. natural language -> VisualIR -> render -> Vision roundtrip;
2. shape/color/position differences are structured;
3. local self-repair converges without rewriting unaffected primitives;
4. every initial/repaired candidate passes through Vision;
5. existing Vision output can be mapped into VisualIR;
6. Motion Primitive state transitions;
7. Skill Graph feedback cycle integrity;
8. Skill Graph end-to-end execution;
9. verifier-first registration into V82 AdaptiveCircuitController;
10. routed execution of the registered visual specialist.

Run:

```bash
python -m compileall -q releases/v83/visual_cognition
python -m unittest discover -s releases/v83/visual_cognition/tests -p "test_*.py" -v
```
