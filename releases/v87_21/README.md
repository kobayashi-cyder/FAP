# FAP V87.21 — Local Image Engine Autodiscovery

V87.21 connects FAP Media Lab to an actually running local Stable Diffusion WebUI-compatible engine without requiring an API key.

Supported local API:
- AUTOMATIC1111;
- Stable Diffusion WebUI Forge-compatible endpoints;
- `GET /sdapi/v1/sd-models`;
- `POST /sdapi/v1/txt2img`.

Default autodiscovery:
- `http://127.0.0.1:7860`
- `http://127.0.0.1:7861`
- `http://localhost:7860`

Security:
- plain HTTP is accepted only for loopback hosts;
- arbitrary LAN/internet HTTP endpoints are rejected;
- the V87.19 general remote adapter remains HTTPS + credential based.

Windows:
1. If A1111/Forge is already installed, run `START_EXISTING_A1111_FOR_FAP.cmd` to look for it in common folders and launch it with API mode.
2. Run `RUN_FAP_V87_21_LOCAL_MEDIA_LAB.cmd`.
3. Open `http://127.0.0.1:11440/`.
4. Enter a prompt and press **FAPで生成**.
5. The returned PNG is persisted, digest-verified and shown directly in the browser.

The local generator is promoted through its own candidate -> testing -> shadow -> active evidence lifecycle after distinct verified generated images.

Boundary:
FAP does not silently install or download multi-gigabyte diffusion model weights. If no existing local A1111/Forge installation/model is present, the Media Lab remains in NEEDS ENGINE state rather than faking a result.

Qwen is not used.
