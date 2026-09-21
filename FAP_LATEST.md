# FAP latest development snapshot

Current mainline: **V87.23 — Compact Offline Distilled Image Path**.

V87.23 follows the fully offline V87.22 runtime with a smaller single-file image path intended for machines where a full large Diffusers checkpoint is impractical.

Current compact path:

`local approved checkpoint -> local config -> from_single_file(local_files_only=True) -> offline inference -> persisted PNG -> actual-file observer -> digest verification -> Media Lab preview`

Offline guarantees:
- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- Hugging Face telemetry disabled;
- `local_files_only=True`;
- non-loopback network connections blocked during inference;
- no provider/API credential required;
- no model download is attempted during offline inference.

Distillation / license policy:
- FAP does not claim to distill proprietary OpenAI/Sol weights;
- unverified teachers and unknown/restricted model licenses are rejected;
- already-distilled checkpoints with permissive license metadata can be admitted through an explicit FAP sidecar manifest;
- the compact reference is `segmind/SSD-1B`, whose public model metadata identifies Apache-2.0 and prior knowledge distillation;
- `black-forest-labs/FLUX.1-schnell` remains the V87.22 permissive timestep-distilled reference for the full local-model path.

V87.23 compact runtime:
- accepts local `.safetensors` / `.ckpt` image checkpoints;
- requires `<checkpoint>.fap.json` with model identity, license, source, config directory, distillation state and pipeline;
- requires the companion Diffusers config to already exist locally;
- rejects checkpoints without the sidecar license gate;
- enables model CPU offload, attention slicing and VAE slicing when supported;
- auto-discovers approved checkpoints from `FAP_OFFLINE_SINGLE_FILES` and common A1111/Forge model directories;
- connects directly to the V87.20 browser Media Lab.

Windows:
- run `RUN_FAP_V87_23_COMPACT_OFFLINE_MEDIA_LAB.cmd`;
- open `http://127.0.0.1:11440/`;
- when an approved local checkpoint and config are present, generation requires no internet connection.

Verification:
- final V87.23 focused tests: **5/5 PASS on Python 3.11**;
- final V87.23 focused tests: **5/5 PASS on Python 3.12**;
- final GitHub Actions run: **35589899804 — SUCCESS**;
- an intermediate run failed only because the newly added manager dependency paths were missing from CI PYTHONPATH; the workflow was corrected without weakening runtime validation.

Operational boundary:
The checkpoint, local Diffusers configuration, Python dependencies and any required runtime libraries must be present before disconnecting from the network. FAP will not fabricate or silently download missing weights.

Implementation:
- `releases/v87_22/offline_native/`;
- `releases/v87_23/compact_offline/`;
- `fap_v87_23_compact_offline_media_lab.py`;
- `RUN_FAP_V87_23_COMPACT_OFFLINE_MEDIA_LAB.cmd`;
- V87.20 Media Lab remains the browser interface.

Promotion history is intentionally sequential through V87.23. Qwen is not used.
