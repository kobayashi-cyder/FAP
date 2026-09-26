# FAP V87.29 — Native Image Engine

V87.29 introduces a FAP-owned image generator that can produce real PNG files
without downloading or loading an external text-to-image checkpoint.

## What is native here

The engine at `fap_native_image.engine.NativeImageEngine` uses only Python
standard-library primitives for its rendering core:

- prompt hashing and deterministic seeds;
- bilingual keyword parsing for basic scene concepts and colors;
- procedural sky / ground / water fields;
- mountains, trees, sun, moon and a simple house primitive;
- seeded abstract / geometric composition fallback;
- a built-in RGB raster buffer;
- a built-in PNG encoder using `struct` + `zlib`;
- SHA-256 addressed artifact storage.

It does **not** call an image-generation API and it does **not** require SSD-1B,
Stable Diffusion, Diffusers, Torch, Pillow, NumPy or a pretrained checkpoint.

## Boundary

This is the first self-owned rendering substrate, not a claim of parity with a
large learned diffusion model. It currently produces procedural / stylized
images. Photorealism, people, animals, complex object topology, typography and
open-world visual knowledge require a later learned native model and training
corpus.

This distinction is intentional: V87.29 establishes a generator FAP owns from
prompt planning through PNG bytes, so later learned modules can replace or
augment individual organs without reintroducing a mandatory external engine.

## Windows

Run:

```text
RUN_FAP_V87_29_NATIVE_IMAGE_LAB.cmd
```

Then open:

```text
http://127.0.0.1:11440/
```

No model preparation step is required.

## Compatibility

V87.29 reuses the verified V87.13-V87.20 media contracts, observer, critic,
portfolio and adaptive fast-path layers. V87.21-V87.24 external/local diffusion
paths remain available separately and are not deleted.

Qwen is not used.

## Verification target

Focused tests verify:

- real PNG signature and dimensions;
- exact SHA-256 binding to the generated artifact;
- different prompts produce different artifacts;
- `external_weights == False`;
- `external_runtime == False`;
- Manager -> observer -> integrity critic -> accepted path.
