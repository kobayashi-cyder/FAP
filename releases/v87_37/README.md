# FAP V87.37 — Sparse End-to-End Execution

V87.37 reconnects the V82 sparse-circuit design to the current V87 media
stack.

## Sparse organ routing

Media requests no longer require the V87.33 -> V87.34 -> V87.36 media gateway
inheritance chain to construct every media organ at process startup.

The current gateway starts from the preserved V87.28-and-earlier text/reasoning
stack and registers three verifier-certified V82 circuits:

- scene -> V87.34 Scene Graph 2;
- cat_morphology -> V87.35 Morphology;
- scientific_dna -> V87.36 Scientific Geometry.

The router uses `top_k=1`. Only the selected media organ is instantiated.
Instances are cached after first use.

## Sparse renderer

V87.32 remains the source of material/shading math, but V87.37 changes the
execution boundary:

- finished studio backgrounds are cached per resolution;
- subject projection creates 32x32 active tiles;
- FXAA runs only on active tiles;
- filmic processing runs only on subject pixels;
- explicit ground faces remain skipped;
- DNA uses a scientific fast renderer without studio background, contact
  shadows or filmic processing.

The triangle rasterizer already works per triangle bounding box rather than
scanning every frame pixel. V87.37 does not yet replace that Python inner loop
with native C/Rust; that remains a later optimization.

## Observable sparsity

Runtime output exposes:
- selected circuit;
- loaded organ set;
- active tile count / total tiles;
- active tile ratio;
- FXAA pixels touched;
- filmic subject pixels;
- background cache hit/miss state.

CI verifies:
- zero media organs loaded at gateway startup;
- one circuit active per media request;
- active tiles are a strict subset for representative cat/DNA renders;
- background reuse on repeated resolution;
- DNA scientific fast path has no full-screen filmic pass.

Run:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Qwen is not used.
