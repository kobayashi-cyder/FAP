# FAP latest development snapshot

Current mainline: **V87.21 — Local Image Engine Autodiscovery**.

V87.21 connects the V87.20 Media Lab to a real locally running AUTOMATIC1111 / Forge-compatible image engine without requiring an API key.

Current local image path:

`Media Lab prompt -> loopback engine autodiscovery -> /sdapi/v1/txt2img -> persisted PNG -> actual-file observer -> digest verification -> browser preview`

New in V87.21:
- automatic loopback discovery of:
  - `http://127.0.0.1:7860`
  - `http://127.0.0.1:7861`
  - `http://localhost:7860`
- AUTOMATIC1111 / Forge-compatible `/sdapi/v1/sd-models` probe;
- real `/sdapi/v1/txt2img` generation;
- no API key required for loopback engines;
- generated PNG bytes are persisted and SHA-256 identified before display;
- local generators participate in FAP candidate -> testing -> shadow -> active promotion;
- V87.19 remote HTTPS engines remain available as fallback/alternative;
- Windows launcher: `RUN_FAP_V87_21_LOCAL_MEDIA_LAB.cmd`;
- existing A1111/Forge launcher helper: `START_EXISTING_A1111_FOR_FAP.cmd`;
- plain HTTP remains restricted to loopback only.

Verification:
- V87.21 focused tests: **5/5 PASS on Python 3.11**
- V87.21 focused tests: **5/5 PASS on Python 3.12**
- GitHub Actions run: **35589200452 — SUCCESS**
- tests cover local model probe, real PNG byte persistence, no-key generation, hybrid manager routing, local skill promotion, and rejection of non-loopback HTTP engines.
- V87.20 focused tests: **5/5 PASS on Python 3.11/3.12**
- V87.19 focused tests: **9/9 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

Operational boundary:
FAP now automatically uses an existing local A1111/Forge installation when it is running with API support. FAP does not silently download multi-gigabyte diffusion model weights. If no compatible local installation/model exists and no V87.19 remote engine is configured, the Media Lab remains in NEEDS ENGINE state rather than fabricating a generated image.

Windows usage:
1. If a local A1111/Forge installation already exists, run `START_EXISTING_A1111_FOR_FAP.cmd`.
2. Run `RUN_FAP_V87_21_LOCAL_MEDIA_LAB.cmd`.
3. Open `http://127.0.0.1:11440/`.
4. Enter an image prompt and press **FAPで生成**.

Implementation:
- `releases/v87_21/local_engine/`
- `fap_v87_21_media_lab.py`
- `RUN_FAP_V87_21_LOCAL_MEDIA_LAB.cmd`
- `START_EXISTING_A1111_FOR_FAP.cmd`
- V87.20 Media Lab remains the browser UI.

Promotion history is intentionally sequential through V87.21. Qwen is not used.
