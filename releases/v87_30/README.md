# FAP V87.30 — Human Rig + Linear Blend Skinning

V87.30 extends the FAP-native image path with an explicit 3D/CAD-like human
representation instead of trying to paint a person directly in 2D.

Pipeline:

```text
prompt
  -> pose/view parser
  -> hierarchical human skeleton
  -> bind pose
  -> continuous tube/ellipsoid body mesh
  -> per-vertex bone weights
  -> Linear Blend Skinning (LBS)
  -> perspective projection
  -> triangle rasterization + z-buffer
  -> simple Lambert shading
  -> built-in PNG encoder
```

## Implemented

- 21-bone hierarchy: pelvis, spine, chest, neck/head, both arms and both legs;
- parent-child transforms so moving a shoulder/hip carries its descendants;
- per-joint XYZ rotation limits;
- bind-pose and inverse-bind matrices;
- multi-bone vertex weights around deformation regions;
- standard LBS deformation:
  `v' = sum(w_i * M_pose_i * inverse(M_bind_i) * v)`;
- connected limb surfaces and torso surface generated from rings;
- head, hands and feet as weighted ellipsoidal geometry;
- prompt-driven basic poses: arms down/up, elbow bend, wave, walk, sit,
  head look left/right;
- front, oblique, side and back views;
- pure-Python perspective renderer, z-buffer, shading and PNG output;
- FAP Media Lab adapter with existing actual-file integrity verification.

## Boundary

This is a geometric human generator, not yet a photorealistic human model.

It improves:
- structural consistency;
- joint hierarchy;
- pose reuse;
- multi-view consistency;
- future animation readiness.

It does not yet provide:
- anatomically detailed face/hands;
- cloth simulation;
- muscles/soft-tissue corrective shapes;
- hair geometry;
- learned texture synthesis;
- photorealistic skin or open-world visual detail.

The next quality layer should be dual-quaternion or corrective-joint deformation,
higher-resolution body topology, hands/face rigs and learned material/texture
modules on top of this stable 3D substrate.

## Windows

Media Lab:

```text
RUN_FAP_V87_30_LBS_IMAGE_LAB.cmd
```

Standalone three-view demo:

```text
RUN_FAP_V87_30_LBS_DEMO.cmd
```

Demo outputs are written under:

```text
runtime/v87_30_lbs_demo/
```

No pretrained checkpoint, image API, Torch, Diffusers, Pillow or NumPy is
required by the LBS renderer. Qwen is not used.
