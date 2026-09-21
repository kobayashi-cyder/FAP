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
