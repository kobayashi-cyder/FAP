# FAP V87.20 — Media Lab

V87.20 makes V87.19 image/video generation visible in a local browser.

Run on Windows:

`RUN_FAP_V87_20_MEDIA_LAB.cmd`

Default UI:

`http://127.0.0.1:11440/`

Visible workflow:

`prompt -> FAP autonomous media skill -> real generator engine -> persisted artifact -> actual-file observer -> verification -> browser image/video preview`

The Media Lab shows:
- image or video mode;
- prompt, dimensions, attempts and hard constraints;
- video duration and FPS;
- configured generation engines and autonomous skill stage;
- actual generated PNG/JPEG/WebP or MP4/WebM preview;
- backend used, generator call count, rounds, MIME and SHA-256 digest;
- operational artifact-integrity verification.

Configuration:
1. provide compatible engine descriptors in `FAP_MEDIA_ENGINES_JSON`;
2. set each descriptor's referenced token environment variable;
3. start the Media Lab;
4. open the localhost UI and press **FAPで生成**.

See `releases/v87_20/FAP_MEDIA_ENGINES.example.json` for the descriptor format.

Engine response contract remains V87.19:
- synchronous completed response with `mime_type` + `data_base64`;
- or queued/running response with a same-origin HTTPS `poll_url`, eventually returning completed media bytes.

Important:
- V87.20 does not ship or impersonate a third-party image/video model.
- If no real engine is configured, the UI explicitly says **生成エンジン未設定**.
- The built-in Lab verifier checks real file persistence and digest identity. It does not label aesthetic/semantic quality as perfect.
- Qwen is not used.
