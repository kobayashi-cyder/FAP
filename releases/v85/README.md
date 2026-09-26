# FAP V85 — Production Vision Host Wiring

V85 turns the V83 Vision adapter boundary into an explicit production host path.

V83 already proved the closed visual loop:

```text
VisualIR -> render -> Vision -> VisualIR -> structured diff -> local repair
```

The missing operational boundary was that constructing `VisualCognitiveLoop()` directly still used `PrimitiveVision` as a dependency-free bootstrap default. V85 adds a canonical production entry point that refuses to start without an explicitly configured production Vision backend.

## Production path

`ProductionVisionHost` requires a `VisionBackend` containing:
- stable backend id;
- an existing Vision callback;
- optional mapper when the backend does not already return `VisualIR`;
- backend kind marked `production`.

The host wraps it with `CallableVisionAdapter` and enforces:
- output must normalize to valid `VisualIR`;
- canvas dimensions must equal the rendered frame;
- bounded rectangle/circle geometry must remain inside the frame;
- `PrimitiveVision` cannot be passed off as a production backend.

`build_production_visual_loop(None)` fails closed instead of silently falling back.

## Existing Vision normalization

`ObjectListVisionMapper` provides a concrete bounded bridge for an existing detector/vision system that returns:

```json
{
  "objects": [
    {"kind":"rect","x":2,"y":3,"w":4,"h":2,"rgb":[255,0,0]},
    {"kind":"circle","x":10,"y":10,"r":3,"rgb":[0,0,255]}
  ]
}
```

This becomes the same V83 `VisualIR` state space used by imagination, drawing, review and repair.

## Bootstrap boundary

`PrimitiveVision` remains available only through the explicitly named `build_bootstrap_visual_loop()` helper for tests/bootstrap use. The V85 production builder never selects it implicitly.

## What V85 does not claim

The repository does not currently contain a separate high-capability production Vision model implementation to bundle. V85 completes the host/injection/normalization contract so such an existing Vision backend can be attached without changing the cognitive loop. It does not relabel the bootstrap verifier as a real production model.
