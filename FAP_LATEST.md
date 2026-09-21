# FAP latest development snapshot

Current mainline: **V87.26 — Option-Conditioned Scientific Reasoner**.

V87.26 keeps the V87.25 structured A-D gateway and adds a conservative scientific hypothesis competition layer.

New path:

```text
explicit A-D answer contract
  -> instruction/content separation
  -> domain inference
  -> A hypothesis: support / contradiction
  -> B hypothesis: support / contradiction
  -> C hypothesis: support / contradiction
  -> D hypothesis: support / contradiction
  -> polarity-aware competition
  -> V87.25 fallback if evidence is weak
  -> contract verification
```

Compatibility rule:
- non-MCQ requests remain on the inherited text path;
- low-confidence scientific questions fall back to V87.25 rather than fabricating certainty;
- V87.13-V87.24 media/offline paths are unchanged;
- Qwen is not used.

Scientific evidence layer:
- compact general textbook relations across physics, chemistry, biology, mathematics and computer science;
- per-option evidence and contradiction traces;
- negative/EXCEPT question polarity;
- minimum evidence and score-margin gates;
- no GPQA answer keys or benchmark-specific answer table.

Verification:
- GitHub Actions **35591888459 — SUCCESS** on Python 3.11 and 3.12;
- per interpreter: V87.26 focused **5/5**, V87.25 focused **6/6**, inherited V87.02-V87.12 text **96/96**, V87.13-V87.24 media/offline **79/79** PASS.

GPQA Diamond:
- Actions **35591758676 — SUCCESS**;
- 198 questions × 4 shuffled repeats = 792 trials;
- parse rate: **100%**;
- score: **208/792 = 26.26%**;
- `option_conditioned_science`: **4/792**;
- unresolved fallback: **788/792**.

The GPQA score is unchanged from V87.25. V87.26 therefore represents verified architectural progress in scientific evidence routing, not a benchmark-accuracy gain. The next bottleneck is knowledge coverage: most GPQA questions still do not retrieve enough native scientific evidence to leave the fallback path.

Implementation:
- `fap_scientific_reasoning.py`
- `fap_v87_26_scientific_reasoning_gateway.py`
- `RUN_FAP_V87_26_SCIENTIFIC_REASONING.cmd`
- `releases/v87_26/`
- `benchmarks/sol_gpqa_v8726.py`

V87.25 and all prior verified functionality remain underneath this release.
