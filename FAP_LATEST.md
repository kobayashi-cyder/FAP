# FAP latest development snapshot

Current mainline: **V87.24 — Verified Offline Bundle Preparation**.

V87.24 closes the setup gap between a legal local distilled image checkpoint and fully disconnected FAP generation.

Two phases are explicitly separated.

One-time connected preparation:
- user reviews and accepts the source model license/terms;
- FAP downloads the pinned `segmind/SSD-1B` A1111 checkpoint;
- source revision is pinned;
- expected file size is pinned;
- SHA-256 is pinned and verified before activation;
- required small Diffusers configuration files are stored locally;
- FAP writes the explicit Apache-2.0 / knowledge-distillation sidecar;
- a corrupted or substituted checkpoint is rejected.

Disconnected inference:
- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- V87.23 loads the checkpoint with `local_files_only=True`;
- non-loopback networking is blocked during inference;
- bundle integrity is re-verified before the Media Lab starts;
- no provider/API credential is required;
- generated PNG artifacts stay local and are displayed through localhost.

Pinned image reference:
- model: `segmind/SSD-1B`;
- checkpoint: `SSD-1B-A1111.safetensors`;
- source revision: `3bbad7fb72248b876d839e6bd0950aa09e3b8bce`;
- license identifier: Apache-2.0;
- public metadata identifies prior knowledge distillation;
- expected size: 4,465,671,322 bytes;
- SHA-256: `1895a00bfc769a00b0c0c43a95e433e79e9db8a85402b45a33e8448785bde94d`.

Windows workflow:
1. while connected once, run `PREPARE_FAP_V87_24_OFFLINE_SSD1B.cmd`;
2. after successful size/SHA verification, disconnect the network;
3. run `RUN_FAP_V87_24_OFFLINE_BUNDLE_MEDIA_LAB.cmd`;
4. open `http://127.0.0.1:11440/`;
5. image generation then uses only the local verified bundle.

Verification:
- V87.24 focused tests: **5/5 PASS on Python 3.11**;
- V87.24 focused tests: **5/5 PASS on Python 3.12**;
- GitHub Actions run: **35590308818 — SUCCESS**;
- tests cover explicit license acceptance, bundle creation, source checksum binding, corruption rejection and refusal to activate the wrong checkpoint.
- V87.23 final tests: **5/5 PASS on Python 3.11/3.12**;
- V87.22 provides the generic fully offline image/video folder-based engine.

Distillation boundary:
FAP does not claim to have freshly distilled GPT-5.6 Sol, OpenAI private weights, or another proprietary teacher. V87.24 uses a public checkpoint whose own metadata identifies it as already knowledge-distilled and Apache-2.0 licensed. Fresh distillation would require a separately lawful teacher, lawful training data, and compute; none is fabricated or assumed.

Operational boundary:
The 4.47 GB checkpoint and Python inference dependencies must be prepared locally before disconnecting. Model weights are intentionally not committed to this Git repository.

Implementation:
- `releases/v87_22/offline_native/`
- `releases/v87_23/compact_offline/`
- `releases/v87_24/offline_bundle/`
- `PREPARE_FAP_V87_24_OFFLINE_SSD1B.cmd`
- `RUN_FAP_V87_24_OFFLINE_BUNDLE_MEDIA_LAB.cmd`

Promotion history is intentionally sequential through V87.24. Qwen is not used.
