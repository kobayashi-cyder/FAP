# FAP latest development snapshot

Current mainline: **V87.32 — Native Photo-Look Renderer**.

V87.32 builds on the V87.31 Scene Graph + Prompt Compliance Gate and targets
the next visible problem: the scene was structurally correct but still looked
like flat CAD geometry.

V87.32 appearance path:

```text
prompt + hard constraints
  -> V87.31 ScenePlan
  -> human / dog geometry
  -> V87.32 surface detail
     - human eyes
     - nose
     - mouth
     - ears
     - hair
  -> smooth vertex normals
  -> palette-aware material response
     - skin
     - cloth
     - fur
     - eyes / nose
     - shoes
  -> key + fill + specular lighting
  -> procedural micro-surface variation
  -> soft contact shadows
  -> studio background / floor
  -> FXAA-like edge smoothing
  -> filmic tone / vignette / fine grain
  -> PNG
  -> artifact integrity
  -> object/layout/style verification
```

Visible result:
- V87.31 comparison image: flat polygon/CAD appearance;
- V87.32 comparison image: smoother surfaces, visible face/hair, softer edges,
  richer dog/human materials, ground contact shadows and more photographic
  studio lighting;
- both human and dog remain present in the same verified scene.

Style semantics:
- active renderer: `photo-look-native`;
- native photo-look capability marker: **0.58**;
- learned refiner: **false**;
- photorealistic verified: **false**.

A `写真風` request therefore remains fail-closed:
- object score: 1.0 when human/dog are present;
- layout score: 1.0 when centered constraint is applied;
- style sub-score: 0.58;
- aggregate score: 0.0 because the existing CompositeCritic forces any fatal
  unmet hard style requirement to zero;
- status: **NOT ACCEPTED**;
- rejection issue: `photorealism_not_yet_verified`.

The 0.58 marker is an implementation-stage capability marker, not a claim of
human-rated photorealism.

Verification:
- GitHub Actions **35603965696 — SUCCESS**;
- Python 3.11: V87.32 focused tests PASS;
- Python 3.12: V87.32 focused tests PASS;
- V87.31 regression: PASS on both interpreters;
- Actions-generated V87.31/V87.32 comparison was visually inspected and shows
  a clear appearance improvement.

Run:

```text
RUN_FAP_V87_32_PHOTO_LOOK_LAB.cmd
```

Implementation:
- `releases/v87_32/photo_look/fap_photo_look/renderer.py`
- `releases/v87_32/photo_look/fap_photo_look/detail.py`
- `releases/v87_32/photo_look/fap_photo_look/engine.py`
- `releases/v87_32/photo_look/fap_photo_look/critic.py`
- `releases/v87_32/photo_look/fap_photo_look/manager.py`
- `releases/v87_32/photo_look/fap_photo_look/runtime.py`
- `web/FAP_Media_Lab_V87_32.html`
- `fap_v87_32_photo_look_lab.py`
- `fap_v87_32_photo_look_demo.py`
- `RUN_FAP_V87_32_PHOTO_LOOK_LAB.cmd`

Boundary:
- this is still native procedural/3D rendering, not a learned diffusion/photo
  model;
- anatomy, hair, cloth and fur are still simplified;
- the next major jump is a **verified learned photo refiner** that takes the
  stable V87.31/V87.32 scene and appearance buffers as conditioning rather than
  inventing the whole scene from scratch.

Compatibility:
- V87.31 Scene Graph and compliance gate remain;
- V87.30 Human LBS remains;
- V87.29 native raster remains;
- V87.28 and earlier reasoning/physics paths remain;
- chat-speed restoration remains;
- Qwen is not used.


## Current mainline chat

The standard chat UI can now run against the current V87.32 mainline facade instead of
stopping at the V87.12 semantic-adaptive backend.

Run:

```text
RUN_FAP_CHAT_LATEST.cmd
```

This starts `fap_v87_32_unified_chat_gateway.py` on the existing chat port and keeps
the same `web/FAP_Chat.html` UI. The UI version badge is populated from
`/api/v1/status`, so it reports `v87.32-unified-chat` when the current
gateway is active.

Routing:
- ordinary conversation and semantic/adaptive memory keep the optimized V87.12 fast path;
- structured MCQ/scientific/physics requests retain the V87.25-V87.28 chain;
- image capability and image generation use the V87.32 native photo-look engine;
- rejected photo-look candidates remain visible for inspection but are not falsely reported
  as accepted;
- Qwen is not used.

Compatibility:
- existing session format and `/api/v1/chat` contract are preserved;
- the old version-specific launchers remain unchanged;
- `RUN_FAP_CHAT_LATEST.cmd` is the stable launcher intended to follow future mainline chat upgrades.
