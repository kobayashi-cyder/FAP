# FAP latest development snapshot

Current mainline: **V87.16 — Observed Media Portfolio Competition**.

V87.16 removes the single-generator bottleneck from the image/video refinement path.

Current media loop:

`prompt -> multiple backends -> observe each actual artifact -> same critic stack -> select best -> defect-scoped repair -> re-compete -> quality gate`

New in V87.16:
- multiple image/video generation backends can compete in parallel lanes;
- every candidate is observation-gated through V87.15 before scoring;
- all candidates are judged by the same critic stack;
- the highest verified non-fatal candidate wins each round;
- one failed backend does not invalidate healthy alternatives;
- if all candidate lanes fail, the portfolio fails closed;
- the best historical candidate is retained if later rounds regress;
- repair prompts are derived from defects in the current best verified candidate;
- the same controller supports both image and video requests.

Verification:
- V87.16 focused tests: **8/8 PASS on Python 3.11**
- V87.16 focused tests: **8/8 PASS on Python 3.12**
- GitHub Actions run: **35586907353 — SUCCESS**
- first V87.16 candidate run correctly failed because the test fixture supplied invalid short artifact digests; production validation was kept strict and the fixture was corrected.
- V87.15 observed-media tests: **8/8 PASS on Python 3.11/3.12**
- V87.14 temporal critic tests: **8/8 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

V87.16 does **not** claim that any bundled generator exceeds a frontier image/video model. It gives FAP a verified mechanism to combine replaceable generators, observe their real outputs, select the strongest evidence-backed candidate, and iteratively refine that candidate rather than inheriting the limitations of one provider.

Implementation:
- `releases/v87_13/media_generation/`
- `releases/v87_14/video_temporal/`
- `releases/v87_15/observed_media/`
- `releases/v87_16/media_portfolio/`

Promotion history is intentionally sequential through V87.16. Qwen is not used.
