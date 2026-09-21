# FAP latest development snapshot

Current mainline: **V87.22 — Offline Native Media Engine**.

V87.22 adds fully local image/video generation using only model files already present on the machine.

Offline guarantees:
- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- Diffusers `local_files_only=True`;
- telemetry disabled;
- non-loopback network creation blocked during inference;
- no provider credential required;
- models are loaded only from `FAP_OFFLINE_MODEL_DIRS`.

License / distillation gate:
- every offline model requires `fap_model_manifest.json`;
- unknown or restricted licenses are rejected;
- initial permissive allowlist includes Apache-2.0, MIT, BSD and CC0;
- proprietary OpenAI weights and unverified teachers are not distilled or copied;
- already-distilled permissive checkpoints can be used directly.

The recommended legal reference image checkpoint is `black-forest-labs/FLUX.1-schnell`, whose model card identifies Apache-2.0 and whose Diffusers documentation identifies it as timestep-distilled.

Generation:
- image pipelines persist PNG;
- video pipelines persist MP4 using local frame encoding;
- the V87.20 browser Media Lab displays the resulting local artifacts;
- no network download is attempted at inference time.

Verification:
- V87.22 focused tests pass on Python 3.11 and 3.12;
- GitHub Actions run **35589651284 — SUCCESS**;
- tests cover permissive-license manifests, rejection of unknown licenses, forced offline environment, blocked non-loopback sockets, local image output and local video output.

Windows:
- set `FAP_OFFLINE_MODEL_DIRS` to local Diffusers model folders;
- run `RUN_FAP_V87_22_OFFLINE_MEDIA_LAB.cmd`;
- open `http://127.0.0.1:11440/`.

Operational boundary:
FAP does not fabricate or silently download model weights. The model and Python dependencies must already exist locally before the network is disconnected.

Promotion history is intentionally sequential through V87.22. Qwen is not used.
