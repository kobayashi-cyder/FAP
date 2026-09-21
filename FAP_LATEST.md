# FAP latest development snapshot

Current mainline: **V87.20 — Media Lab**.

V87.20 makes the V87.19 autonomous image/video generation path visible in a local browser.

Visible workflow:

`prompt -> autonomous media skill -> real generator engine -> persisted artifact -> actual-file observer -> verification -> browser preview`

New in V87.20:
- local browser UI at `http://127.0.0.1:11440/`;
- Windows launcher: `RUN_FAP_V87_20_MEDIA_LAB.cmd`;
- image/video mode selector;
- prompt, dimensions, max attempts and hard constraints;
- video duration and FPS controls;
- engine/skill status display;
- generated PNG/JPEG/WebP preview;
- generated MP4/WebM browser playback;
- backend ID, generation call count, rounds, MIME, SHA-256 digest and verification result;
- secure artifact serving with path traversal protection;
- explicit `生成エンジン未設定` state when no real provider is configured.

Verification:
- V87.20 focused tests: **5/5 PASS on Python 3.11**
- V87.20 focused tests: **5/5 PASS on Python 3.12**
- GitHub Actions run: **35588813512 — SUCCESS**
- tests cover browser UI/status serving, real persisted image bytes, asynchronous video bytes, artifact retrieval and traversal protection.
- V87.19 focused tests: **9/9 PASS on Python 3.11/3.12**
- V87.18 focused tests: **6/6 PASS on Python 3.11/3.12**
- V87.17 focused tests: **7/7 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

Operational boundary:
V87.20 supplies the viewing/generation environment but still requires at least one compatible real image or video generation engine configured through `FAP_MEDIA_ENGINES_JSON` and the referenced credential environment variable. If none is configured, the UI does not fake a generated result.

The built-in Media Lab verifier checks actual artifact persistence and SHA-256 identity. It is an operational integrity verifier, not a claim of semantic or aesthetic perfection.

Implementation:
- `releases/v87_19/autonomous_media/`
- `releases/v87_20/media_lab/`
- `web/FAP_Media_Lab.html`
- `fap_v87_20_media_lab.py`
- `RUN_FAP_V87_20_MEDIA_LAB.cmd`

Promotion history is intentionally sequential through V87.20. Qwen is not used.
