# FAP V87.24 — Verified Offline Bundle Preparation

V87.24 closes the setup gap for V87.23.

There are two explicitly separated phases.

1. One-time connected preparation:
   - user reviews and accepts the model license;
   - FAP downloads the pinned SSD-1B A1111 checkpoint;
   - small local Diffusers configuration files are downloaded;
   - checkpoint size and SHA-256 are verified;
   - the Apache-2.0 / knowledge-distillation sidecar is generated;
   - the bundle becomes offline-ready only after verification.

2. Disconnected inference:
   - HF_HUB_OFFLINE=1;
   - TRANSFORMERS_OFFLINE=1;
   - V87.23 local_files_only=True;
   - non-loopback networking is blocked during inference;
   - bundle checksum is re-verified before startup;
   - the browser Media Lab serves generated PNG files locally.

Pinned reference:
- model: segmind/SSD-1B
- checkpoint: SSD-1B-A1111.safetensors
- source revision: 3bbad7fb72248b876d839e6bd0950aa09e3b8bce
- license identifier: Apache-2.0
- model metadata identifies prior knowledge distillation
- expected checkpoint size: 4,465,671,322 bytes
- SHA-256: 1895a00bfc769a00b0c0c43a95e433e79e9db8a85402b45a33e8448785bde94d

Windows:
- connected once: PREPARE_FAP_V87_24_OFFLINE_SSD1B.cmd
- disconnect network
- run: RUN_FAP_V87_24_OFFLINE_BUNDLE_MEDIA_LAB.cmd
- UI: http://127.0.0.1:11440/

Important:
- model weights are not committed into the FAP Git repository;
- FAP does not accept an unverified or corrupted checkpoint;
- Python inference dependencies such as torch, diffusers, transformers, accelerate and safetensors still need to be locally installed before disconnected inference;
- Qwen is not used.
