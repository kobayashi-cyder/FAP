# FAP V87.26 — Option-Conditioned Scientific Reasoner

V87.26 builds on the V87.25 structured MCQ lane.

Instead of jumping directly from question to one answer, FAP now evaluates each option as a separate scientific hypothesis:

```text
question
  -> A: support / contradiction
  -> B: support / contradiction
  -> C: support / contradiction
  -> D: support / contradiction
  -> polarity-aware competition
  -> answer contract
```

This stage uses a compact set of general textbook scientific relations across physics, chemistry, biology, mathematics and computer science. It contains no GPQA answer keys and no benchmark-specific answer table.

Conservative boundary:
- science evidence must exceed a minimum strength and margin;
- otherwise V87.25's unresolved fallback remains authoritative;
- evidence-based decisions are still marked PARTIAL unless independently answer-key verified;
- non-MCQ requests remain on the inherited path;
- V87.24 and all earlier media/offline paths are untouched;
- Qwen is not used.
