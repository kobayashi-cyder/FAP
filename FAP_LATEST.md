# FAP latest development snapshot

Current mainline: **V87.37 — Sparse End-to-End Execution**.

V87.37 reconnects the V82 sparse-circuit design to the current V87 media
stack instead of allowing later media generations to become increasingly dense
at runtime.

Core changes:
- V82 verifier-first SparseRouter selects one media organ with `top_k=1`;
- media organs are lazy: scene, cat morphology and scientific DNA are not
  instantiated at normal chat startup;
- the selected organ is cached after first use;
- V87.32 material/shading math is preserved, but post-processing is restricted
  to 32x32 active screen tiles;
- finished studio backgrounds are cached per resolution;
- FXAA runs only on active tiles;
- filmic processing runs only on subject pixels;
- DNA uses a scientific fast renderer with no studio background, contact
  shadows or filmic pass;
- the launcher polls readiness instead of sleeping for a fixed two seconds.

Current routed organs:
- scene -> V87.34 Scene Graph 2;
- cat_morphology -> V87.35 Morphology;
- scientific_dna -> V87.36 Scientific Geometry.

Sparsity is observable in runtime metadata:
- selected circuit / score;
- loaded organ set;
- active tiles / total tiles;
- active tile ratio;
- FXAA pixels touched;
- filmic subject pixels;
- background-cache state.

Important boundary:
- V87.37 makes routing, organ loading and screen-space post-processing sparse;
- V87.32's triangle rasterizer already operates inside each triangle bounding
  box, but its Python inner pixel loop is not yet replaced by native C/Rust;
- V87.35 coat painting still processes the relevant mesh faces in Python;
- therefore this is a substantial sparse-execution step, not a claim that every
  low-level operation is now sparse/native.

Run:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Compatibility:
- V87.36 Scientific DNA remains;
- V87.35 Cat Morphology remains;
- V87.34 Scene Graph 2 remains;
- V87.33 Object Registry remains;
- V87.32 material/shading behavior remains as the general visual base;
- V87.28 and earlier reasoning/physics paths remain;
- previous chat-speed restoration remains;
- Qwen is not used.
