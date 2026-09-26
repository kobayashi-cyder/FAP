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

## Verification

GitHub Actions run **35591748555 — SUCCESS** on Python 3.11 and 3.12.

Per interpreter:
- V87.26 focused tests: **5/5 PASS**;
- V87.25 focused regression: **6/6 PASS**;
- inherited V87.02-V87.12 text regression: **96/96 PASS**;
- V87.13-V87.24 media/offline regression: **79/79 PASS**.

GPQA Diamond run **35591758676 — SUCCESS**:
- 198 questions × 4 shuffled repeats = 792 trials;
- parse rate: **100%**;
- score: **208/792 = 26.26%**;
- `option_conditioned_science`: **4/792**;
- unresolved fallback: **788/792**.

The score is unchanged from V87.25. V87.26 therefore establishes a real evidence-conditioned scientific lane without claiming a benchmark accuracy gain. The next bottleneck is scientific knowledge coverage, especially chemistry, physics and general-domain questions.
