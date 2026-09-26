# FAP V87.28 — Expanded Deterministic Physics Solvers

V87.28 extends the verified V87.27 physics substrate with additional equation-based solvers.

New deterministic families:
- Newton's second law;
- linear momentum;
- gravitational potential energy;
- centripetal acceleration;
- wave speed;
- electromagnetic frequency from wavelength;
- de Broglie wavelength;
- Coulomb force;
- ideal-gas pressure;
- Wien peak wavelength;
- Stefan-Boltzmann flux;
- radioactive half-life;
- Ohm's law;
- electric power.

Each solver requires explicit semantic cues, required variables, compatible units, and a unique close answer choice. If those guards do not pass, V87.28 delegates to V87.27 unchanged.

No benchmark-specific question text or answer keys are embedded. Qwen is not used.


## Verification

GitHub Actions **35596410727 — SUCCESS** on Python 3.11 and 3.12.

Per interpreter:
- V87.28 focused solvers: **10/10 PASS**;
- V87.27 physics regression: **12/12 PASS**;
- V87.26 focused regression: **5/5 PASS**;
- V87.25 focused regression: **6/6 PASS**;
- inherited V87.02-V87.12 text: **96/96 PASS**;
- V87.13-V87.24 media/offline: **79/79 PASS**.

GPQA Diamond comparison **35596419295 — SUCCESS**:
- V87.27: **208/792 = 26.26%**;
- V87.28: **208/792 = 26.26%**;
- parse rate: **100%**;
- changed predictions: **0**;
- changed-to-correct: **0**;
- changed-to-wrong: **0**;
- V87.28 solver activations on GPQA: **0**.

Therefore V87.28 is a verified general-physics capability expansion, not a GPQA accuracy improvement.
