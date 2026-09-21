# FAP latest development snapshot

Current mainline: **V87.17 — Adaptive Media Fast Path**.

V87.17 reduces the number of generation/observation transitions needed to reach the same verified quality gate.

Current fast path:

`best-known lane first -> observe actual artifact -> critic -> accept immediately if gate passes -> expand only on miss`

When repair is needed:

`repair best verified defects -> retry a narrow lane set -> expand only if still insufficient`

New in V87.17:
- historically strongest observed backend is attempted first;
- if that candidate clears the unchanged quality gate, remaining backends are skipped;
- full portfolio competition remains available as fallback;
- repair rounds restart narrow before re-expanding;
- lightweight lane profiles learn score EMA, acceptance reliability, and failure rate;
- successful/reliable lanes move forward automatically;
- unreliable lanes are deprioritized without being removed;
- image and video use the same adaptive routing path.

Transition effect:
- with N configured backends, an easy/common request can fall from N generator/observer calls to **1**;
- difficult requests retain the V87.16 portfolio fallback;
- critic and observation gates are not weakened.

Verification:
- V87.17 focused tests: **7/7 PASS on Python 3.11**
- V87.17 focused tests: **7/7 PASS on Python 3.12**
- GitHub Actions run: **35587260082 — SUCCESS**
- V87.16 focused tests: **8/8 PASS on Python 3.11/3.12**
- V87.15 observed-media tests: **8/8 PASS on Python 3.11/3.12**
- V87.14 temporal critic tests: **8/8 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

V87.17 is aimed at outperforming stronger systems first on **verified completion efficiency**: reaching an accepted artifact with fewer generation/observation transitions while preserving the same evidence-backed gate. It does **not** yet claim universal quality superiority over GPT-5.6 Sol or a frontier image/video generator; that requires an identical-prompt head-to-head benchmark.

Implementation:
- `releases/v87_13/media_generation/`
- `releases/v87_14/video_temporal/`
- `releases/v87_15/observed_media/`
- `releases/v87_16/media_portfolio/`
- `releases/v87_17/adaptive_fast_path/`

Promotion history is intentionally sequential through V87.17. Qwen is not used.
