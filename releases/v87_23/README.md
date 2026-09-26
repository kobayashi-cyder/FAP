# FAP V87.23 — Compact Offline Distilled Image Path

V87.23 follows V87.22 with a smaller single-file offline image path.

Reference checkpoint:
- `segmind/SSD-1B`;
- Hugging Face model card: Apache-2.0;
- model card labels it as a distilled / knowledge-distillation model;
- the A1111-format checkpoint is approximately 4.47 GB.

Why:
- FLUX.1-schnell is permissive and timestep-distilled, but its full checkpoint is much larger;
- SSD-1B gives FAP a more compact legally permissive distilled image option for local machines.

Runtime:
- reads a local `.safetensors` or `.ckpt`;
- requires a local companion Diffusers config directory;
- requires a sidecar `<checkpoint>.fap.json`;
- uses Diffusers `from_single_file(..., config=<local>, local_files_only=True)`;
- blocks non-loopback network access during inference;
- enables model CPU offload, attention slicing and VAE slicing when the installed pipeline supports them;
- persists the generated PNG locally.

Autodiscovery:
- `FAP_OFFLINE_SINGLE_FILES`;
- common A1111 / Forge model directories;
- only checkpoints with an explicit FAP license sidecar are admitted.

This is not a new distillation of proprietary models. It uses a checkpoint whose public metadata already identifies a permissive license and prior knowledge distillation.

Qwen is not used.
