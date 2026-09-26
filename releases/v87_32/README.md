# FAP V87.32 — Native Photo-Look Renderer

V87.32 builds on the V87.31 Scene Graph. It does **not** replace semantic
verification and it does not claim learned photorealism.

The goal of this release is to remove obvious flat-CAD appearance before a
learned photo refiner is introduced.

## Added appearance pipeline

```text
V87.31 ScenePlan
  -> human / dog geometry
  -> surface-detail augmentation
     - human eyes
     - nose
     - mouth
     - ears
     - hair cap
  -> smooth vertex normals
  -> palette-aware material profiles
     - skin
     - cloth
     - fur
     - eyes/nose
     - shoes
  -> wrapped key light + fill light + specular response
  -> procedural micro-surface variation
  -> soft contact shadows
  -> studio background / floor
  -> FXAA-like edge smoothing
  -> filmic tone / vignette / fine grain
  -> PNG
  -> artifact integrity + prompt/style gate
```

## Style semantics

V87.31:
- renderer: `geometric-3d`;
- photo-style capability: effectively unavailable.

V87.32:
- renderer: `photo-look-native`;
- native photo-look capability marker: **0.58**;
- learned refiner: **false**;
- photorealistic verified: **false**.

Therefore a request such as `写真風` still fails closed. The score is no
longer 0.0 because meaningful appearance work is present, but it is not allowed
to become `accepted` until a genuinely verified learned photo renderer exists.

The 0.58 value is a capability marker for this implementation stage, not a
claim of human-rated photorealism.

## Why this is useful

The learned stage that comes next will receive:
- structurally correct human/dog scenes;
- smoother surface normals;
- richer native materials;
- shadows and camera-space appearance cues;
- explicit object/layout/style metadata;
- a fail-closed verifier.

That makes the learned refiner a finishing stage rather than asking it to invent
all geometry, composition and verification from scratch.

## Run on Windows

```text
RUN_FAP_V87_32_PHOTO_LOOK_LAB.cmd
```

No external image API, pretrained checkpoint, Torch, Diffusers, Pillow or NumPy
is required by the V87.32 native renderer. Qwen is not used.
