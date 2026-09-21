# FAP latest development snapshot

Current mainline: **V87.30 — Human Rig + Linear Blend Skinning**.

V87.30 extends the FAP-native image generation path with a geometric 3D/CAD-like
human substrate. Instead of painting a human directly in 2D, FAP now constructs
an articulated body, deforms it in 3D and renders the resulting surface.

Native human image path:

```text
prompt
  -> pose / view interpretation
  -> 21-bone hierarchical skeleton
  -> bind pose + inverse-bind transforms
  -> connected body mesh
  -> per-vertex bone weights
  -> Linear Blend Skinning (LBS)
  -> perspective projection
  -> triangle rasterization + z-buffer
  -> Lambert-style shading
  -> native PNG bytes
  -> existing FAP artifact-integrity verification
```

Implemented in V87.30:
- pelvis/spine/chest/neck/head hierarchy;
- bilateral shoulder/elbow/wrist/hand chains;
- bilateral hip/knee/ankle/foot chains;
- XYZ joint limits;
- bind and inverse-bind transforms;
- multi-bone vertex weighting near joints;
- standard LBS deformation;
- connected ring-based torso and limb surfaces;
- weighted head/hands/feet geometry;
- prompt-driven arm, elbow, walking, sitting and head poses;
- front, oblique, side and back camera views;
- pure-Python software 3D rendering with a depth buffer;
- PNG generation without an external image checkpoint;
- Media Lab integration and Windows launchers.

Verification:
- GitHub Actions **35599407955 — SUCCESS**;
- Python 3.11: **7/7 PASS**;
- Python 3.12: **7/7 PASS**;
- verified descendant motion under parent-bone rotation;
- verified multi-bone weights;
- verified non-trivial LBS surface deformation;
- verified PNG dimensions/signature;
- verified prompt-dependent pose/view output;
- verified Media Lab artifact-integrity acceptance.

Boundary:
- this is a geometric/stylized human renderer, not photorealistic synthesis;
- face, hands, hair, cloth and soft-tissue anatomy remain coarse;
- there is no learned texture/material synthesis yet;
- the next deformation-quality step is corrective shapes or dual-quaternion
  skinning around difficult joints.

Compatibility:
- V87.29 native prompt-to-raster generation remains available;
- V87.28 deterministic physics and earlier verified reasoning/media paths remain;
- no external image API or pretrained image checkpoint is required for V87.30;
- Qwen is not used.

Implementation:
- `releases/v87_30/human_lbs/fap_human_lbs/core.py`
- `releases/v87_30/human_lbs/fap_human_lbs/engine.py`
- `releases/v87_30/human_lbs/fap_human_lbs/manager.py`
- `fap_v87_30_lbs_image_lab.py`
- `fap_v87_30_lbs_demo.py`
- `RUN_FAP_V87_30_LBS_IMAGE_LAB.cmd`
- `RUN_FAP_V87_30_LBS_DEMO.cmd`

V87.29 and all prior functionality remain underneath this release.
