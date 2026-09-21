# FAP latest development snapshot

Current mainline: **V87.18 — Critic Cascade**.

V87.18 reduces evaluation transitions without weakening the acceptance gate.

Current fast path:

`best-known lane -> observe actual artifact -> cheap critic stage -> expensive stages only when needed -> accept / repair / expand`

New in V87.18:
- cheap critics run before expensive critics;
- fatal evidence short-circuits immediately;
- candidates clearly below an early continue floor skip later expensive critics;
- candidates that survive early stages still run the full configured critic stack;
- completed quality remains the minimum score across required evaluated stages;
- therefore rejection becomes cheaper while acceptance remains fully verified.

Combined V87.17 + V87.18 effect:
- unnecessary generator/observer lanes are skipped;
- unnecessary expensive critic stages are skipped;
- full portfolio and full critic stacks remain available when needed;
- no evidence gate is weakened.

Verification:
- V87.18 focused tests: **6/6 PASS on Python 3.11**
- V87.18 focused tests: **6/6 PASS on Python 3.12**
- GitHub Actions run: **35587408504 — SUCCESS at test step**
- V87.17 focused tests: **7/7 PASS on Python 3.11/3.12**
- V87.16 focused tests: **8/8 PASS on Python 3.11/3.12**
- V87.15 observed-media tests: **8/8 PASS on Python 3.11/3.12**
- V87.14 temporal critic tests: **8/8 PASS on Python 3.11/3.12**
- prior V87.12 runtime suite: **91/91 PASS**

The shortest path to surpassing GPT-5.6 Sol is not to compete first on raw one-shot model size. FAP is targeting **verified completion efficiency** first: reach an accepted artifact with fewer generation, observation, critique, and repair transitions. Universal quality superiority still requires an identical-prompt head-to-head benchmark.

Implementation:
- `releases/v87_13/media_generation/`
- `releases/v87_14/video_temporal/`
- `releases/v87_15/observed_media/`
- `releases/v87_16/media_portfolio/`
- `releases/v87_17/adaptive_fast_path/`
- `releases/v87_18/critic_cascade/`

Promotion history is intentionally sequential through V87.18. Qwen is not used.
