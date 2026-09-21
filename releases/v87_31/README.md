# FAP V87.31 — Scene Graph + Prompt Compliance Gate

V87.31 fixes a correctness problem exposed by the Media Lab screenshot:

```text
Prompt: 人と犬
Hard constraint: 写真風
Old result: human-only geometric image -> accepted / integrity 1.0
```

That result proved only that a PNG existed and its digest matched. It did not
prove that the requested scene or style had been generated.

V87.31 separates those concepts.

## Pipeline

```text
prompt + hard constraints
  -> ScenePlan
  -> required object extraction
  -> human geometry / dog geometry
  -> scene composition
  -> native 3D rasterization
  -> actual-file integrity observation
  -> SceneQualityCritic
       - required-object gate
       - centered-layout gate
       - requested-style capability gate
  -> accepted only if every gate passes
```

## New native scene coverage

- human: V87.30 articulated Human LBS;
- dog: new native beagle-like quadruped geometry;
- multi-object scene: human + dog in one 3D render;
- V87.29 procedural raster is retained as fallback when no supported semantic
  scene object is requested.

## Correct acceptance semantics

For `人と犬`:

- human generated: yes;
- dog generated: yes;
- structural object score: 1.0;
- accepted: yes, unless another hard constraint fails.

For `人と犬 + 写真風`:

- human generated: yes;
- dog generated: yes;
- artifact integrity: 1.0 when bytes/digest are valid;
- object score: 1.0;
- style score: **0.0** because the current renderer is geometric-3D;
- accepted: **no**.

This is intentional. V87.31 does not claim photorealism that it cannot produce.

## UI

`RUN_FAP_V87_31_SCENE_IMAGE_LAB.cmd`

The V87.31 UI reports separately:

- integrity;
- objects;
- layout;
- style;
- required/generated objects;
- requested/render style;
- explicit rejection issues.

The old hard-coded V87.20 badge is not used by this launcher.

## Boundary

The new dog is explicit native geometry, not a learned animal generator.
Photorealistic people/animals still require a later learned rendering/texture
layer. V87.31 establishes the scene representation and fail-closed quality gate
needed before that layer can be trusted.

No Qwen component is used.
