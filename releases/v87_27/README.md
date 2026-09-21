# FAP V87.27 — Physics Knowledge Store

V87.27 starts the native knowledge expansion with physics.

The store is structured as:
- concepts and aliases;
- canonical claims;
- common misconceptions;
- formulas;
- applicability conditions;
- support / contradiction patterns.

Coverage starts with quantum mechanics, particle physics, mechanics, electromagnetism, thermodynamics/statistical physics, relativity, nuclear physics, optics and condensed matter.

Runtime:
```text
physics MCQ
  -> retrieve relevant physics entries
  -> score each A-D hypothesis against claims/misconceptions
  -> require evidence strength + margin
  -> answer if supported
  -> otherwise fall back to V87.26
```

No GPQA answer keys or benchmark-specific answer table are stored. Non-physics MCQs remain on V87.26. All prior text/media paths remain unchanged. Qwen is not used.


## Verification

GitHub Actions **35595452457 — SUCCESS** on Python 3.11 and 3.12.

Per interpreter:
- V87.27 focused physics tests: **12/12 PASS**;
- V87.26 focused regression: **5/5 PASS**;
- V87.25 focused regression: **6/6 PASS**;
- inherited V87.02-V87.12 text: **96/96 PASS**;
- V87.13-V87.24 media/offline: **79/79 PASS**.

Default GPQA run **35595452463 — SUCCESS**:
- V87.26: **208/792 = 26.26%**;
- V87.27 default: **208/792 = 26.26%**;
- changed predictions: **0**;
- parse rate remains 100%.

The default score is intentionally unchanged. Two narrow research solvers produced +8 dev-only correct trials during development, but had zero holdout coverage, so they are quarantined behind `FAP_EXPERIMENTAL_NARROW_PHYSICS=1` and are not part of the default benchmark/runtime claim.

Default V87.27 includes:
- structured physics knowledge retrieval in advisory-only mode;
- deterministic general solvers for photon energy/wavelength, Lorentz gamma, Hubble recession velocity, Schwarzschild radius, and classical kinetic energy;
- strict fallback to V87.26 when no deterministic solution is available.

This release is a physics reasoning substrate expansion, not yet a GPQA accuracy improvement.
