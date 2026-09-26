# FAP V87.22 — Offline Native Media Engine

V87.22 adds a no-network generation path that reads only local model weights.

Runtime guarantees:
- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- `local_files_only=True`;
- Hugging Face telemetry disabled;
- non-loopback socket creation is blocked during inference;
- model paths come only from `FAP_OFFLINE_MODEL_DIRS`;
- no provider credential is needed.

Each model folder must contain:
- `model_index.json`;
- `fap_model_manifest.json`.

FAP refuses to execute local weights whose manifest license is not on the offline allowlist. The initial allowlist covers permissive licenses such as Apache-2.0, MIT, BSD and CC0.

## Distillation decision

FAP does not attempt to distill proprietary OpenAI weights or unverified teachers.

For the image path, the recommended legal reference is `black-forest-labs/FLUX.1-schnell`:
- its public model card identifies Apache-2.0;
- Diffusers identifies it as timestep-distilled;
- therefore V87.22 treats it as an already-distilled permissive checkpoint rather than performing a new teacher-copying process.

Copy `FLUX1_SCHNELL_MANIFEST.example.json` to the local model directory as `fap_model_manifest.json` after independently obtaining the model under its license/access terms.

## Offline image/video support

The engine is generic:
- image pipelines return `images` and are persisted as PNG;
- video pipelines return `frames` and are encoded locally to MP4;
- video encoding requires locally installed `imageio` with FFmpeg support;
- no download is attempted at inference time.

## Windows

Set `FAP_OFFLINE_MODEL_DIRS` to one or more local model directories, then run:

`RUN_FAP_V87_22_OFFLINE_MEDIA_LAB.cmd`

Open:

`http://127.0.0.1:11440/`

If the model or dependency is not already present locally, FAP reports NEEDS MODEL rather than connecting to the internet.

Qwen is not used.
