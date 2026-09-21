# FAP latest development snapshot

Current mainline: **V87.27 — Physics Knowledge Substrate**.

V87.27 starts the native physics expansion on top of V87.26 without replacing existing routing.

Default physics path:

```text
explicit A-D MCQ
  -> deterministic physics solver (strict semantic/unit guards)
  -> if unresolved: physics knowledge retrieval (advisory-only)
  -> inherited V87.26 structured science path
  -> answer contract verification
```

What is new:
- structured physics knowledge covering quantum mechanics, particle physics, mechanics, electromagnetism, thermodynamics/statistical physics, relativity, nuclear physics, optics and condensed matter;
- concepts, aliases, canonical claims, misconceptions, formulas and applicability conditions;
- retrieval traces per answer option;
- general deterministic solvers for photon energy from wavelength, Lorentz gamma, Hubble recession velocity, Schwarzschild radius, and classical kinetic energy;
- deterministic solvers run before broad domain routing, so a physics problem mislabeled as `general` can still be solved.

Safety / anti-overfit boundary:
- heuristic physics retrieval is **advisory-only** and cannot independently override the inherited answer;
- two narrow research solvers that produced dev-only gains are quarantined behind `FAP_EXPERIMENTAL_NARROW_PHYSICS=1`;
- those dev-only gains are excluded from the default runtime and benchmark claim;
- no GPQA answer table is embedded;
- Qwen is not used.

Verification:
- branch Actions **35595452457 — SUCCESS** on Python 3.11 and 3.12;
- per interpreter: V87.27 focused **12/12**, V87.26 focused **5/5**, V87.25 focused **6/6**, inherited V87.02-V87.12 text **96/96**, V87.13-V87.24 media/offline **79/79** PASS.

Default GPQA Diamond:
- Actions **35595452463 — SUCCESS**;
- V87.26: **208/792 = 26.26%**;
- V87.27 default: **208/792 = 26.26%**;
- parse rate: **100%**;
- changed predictions: **0**.

During development, two narrow deterministic solvers changed 8 dev-split trials and solved all 8 correctly, but they had **zero holdout coverage**. They are therefore not enabled by default and are not counted as evidence of general reasoning improvement.

Implementation:
- `fap_physics_knowledge.py`
- `fap_physics_numeric.py`
- `fap_v87_27_physics_knowledge_gateway.py`
- `RUN_FAP_V87_27_PHYSICS_KNOWLEDGE.cmd`
- `releases/v87_27/`
- `benchmarks/sol_gpqa_v8727.py`

V87.26 and all prior verified functionality remain underneath this release.
