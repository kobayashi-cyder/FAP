# FAP latest development snapshot

Current mainline: **V87.31 — Scene Graph + Prompt Compliance Gate**.

V87.31 fixes the image-generation correctness issue exposed by the Media Lab
case `人と犬` with a `写真風` hard constraint.

Previous behavior could produce a human-only geometric PNG and still report
`accepted` because the verifier checked only real bytes and digest identity.

V87.31 separates artifact validity from prompt compliance.

Native scene path:

```text
prompt + hard constraints
  -> ScenePlan
  -> required object extraction
  -> human / dog scene geometry
  -> multi-object composition
  -> native 3D rasterization
  -> actual-file integrity
  -> required-object gate
  -> centered-layout gate
  -> style-capability gate
  -> accepted only when every gate passes
```

Implemented:
- human + dog multi-object scene generation;
- new FAP-native beagle-like quadruped geometry;
- V87.30 Human LBS retained for the human;
- V87.29 procedural raster retained as fallback for prompts outside the current
  explicit scene-object vocabulary;
- required/generated object tracking;
- unsupported-object fail-closed behavior;
- centered-subject hard-constraint tracking;
- photorealistic style detection;
- explicit rejection when photorealism is requested but unavailable;
- rejected artifacts remain visible for inspection;
- new V87.31 Media Lab UI showing integrity/object/layout/style separately;
- UI version comes from V87.31 status instead of the old hard-coded V87.20 badge.

Screenshot-case verification:
- `人と犬 + 被写体を中央に保つ`: **accepted**, score 1.0;
- generated objects: **human, dog**;
- `人と犬 + 被写体を中央に保つ + 写真風`: **rejected**, score 0.0;
- rejection: `photorealistic_style_unavailable`;
- artifact still returned so the failed candidate can be visually inspected.

Verification:
- GitHub Actions **35602627509**;
- Python 3.11: V87.31 focused tests PASS, V87.30 regression PASS;
- Python 3.12: V87.31 focused tests PASS, V87.30 regression PASS;
- Actions-generated human/dog sample visually confirms both subjects are present.

Boundary:
- the dog is explicit native geometry, not a learned animal model;
- the human remains geometric/stylized;
- photorealistic people/animals are **not yet available**;
- V87.31 deliberately rejects a photo-style request rather than falsely
  labeling geometric output as successful.

Run:

```text
RUN_FAP_V87_31_SCENE_IMAGE_LAB.cmd
```

Implementation:
- `releases/v87_31/scene_image/fap_scene_image/scene.py`
- `releases/v87_31/scene_image/fap_scene_image/engine.py`
- `releases/v87_31/scene_image/fap_scene_image/critic.py`
- `releases/v87_31/scene_image/fap_scene_image/manager.py`
- `releases/v87_31/scene_image/fap_scene_image/runtime.py`
- `web/FAP_Media_Lab_V87_31.html`
- `fap_v87_31_scene_image_lab.py`
- `fap_v87_31_scene_demo.py`
- `RUN_FAP_V87_31_SCENE_IMAGE_LAB.cmd`

Compatibility:
- V87.30 Human LBS remains available;
- V87.29 native raster remains available;
- V87.28 and earlier reasoning/physics paths remain;
- chat-speed restoration remains;
- Qwen is not used.
