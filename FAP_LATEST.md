# FAP latest development snapshot

Current mainline: **V87.28 — Expanded Deterministic Physics Solvers**.

V87.28 extends the verified V87.27 physics substrate with additional equation-based solvers while preserving all prior routing and media paths.

Default physics path:

```text
explicit A-D MCQ
  -> V87.28 deterministic physics equation solvers
  -> if unresolved: V87.27 deterministic physics solvers
  -> advisory physics knowledge retrieval
  -> inherited V87.26 structured science path
  -> answer contract verification
```

New deterministic solver families:
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

Safety / anti-overfit boundary:
- each solver requires explicit semantic cues, required variables, compatible units, and a unique close answer choice;
- unresolved inputs delegate to V87.27 unchanged;
- no benchmark-specific question text or answer keys are embedded;
- Qwen is not used.

Verification:
- branch Actions **35596410727 — SUCCESS** on Python 3.11 and 3.12;
- per interpreter: V87.28 focused **10/10**, V87.27 focused **12/12**, V87.26 focused **5/5**, V87.25 focused **6/6**, inherited V87.02-V87.12 text **96/96**, V87.13-V87.24 media/offline **79/79** PASS.

GPQA Diamond comparison:
- Actions **35596419295 — SUCCESS**;
- V87.27: **208/792 = 26.26%**;
- V87.28: **208/792 = 26.26%**;
- parse rate: **100%**;
- changed predictions: **0**;
- changed-to-correct: **0**;
- changed-to-wrong: **0**;
- V87.28 solver activations on GPQA: **0**.

The benchmark score is unchanged. V87.28 is therefore a verified general-physics capability expansion, not a GPQA accuracy improvement.

Implementation:
- `fap_physics_solver_v2.py`
- `fap_v87_28_physics_solver_gateway.py`
- `RUN_FAP_V87_28_PHYSICS_SOLVERS.cmd`
- `releases/v87_28/`
- `benchmarks/sol_gpqa_v8728.py`

V87.27 and all prior verified functionality remain underneath this release.
