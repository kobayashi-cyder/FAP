# FAP latest development snapshot

Current mainline: **V87.25 — Structured Benchmark Reasoning Gateway**.

V87.25 is rebased on the verified V87.24 mainline and adds a narrow structured A-D question lane without replacing existing FAP routing.

New path:

```text
explicit A-D answer contract
  -> instruction/content separation
  -> choice parsing
  -> domain inference
  -> bounded reasoning
  -> contract verification
```

Compatibility rule:
- only explicit four-choice A-D requests with a multiple-choice/answer contract enter the new lane;
- every other request delegates to the inherited V87.12 text path unchanged;
- V87.24 offline-bundle preparation and all prior media paths remain unchanged.

Why this was added:
The V87.18 GPQA Diamond measurement produced 0/792 with a 0% parse rate because benchmark questions could be hijacked by keyword routing and did not satisfy the required `Answer: $LETTER` output contract.

V87.25 measurement:
- GPQA Diamond: 198 questions × 4 shuffled repeats = 792 trials;
- parse rate: **100%**;
- measured score: **208/792 = 26.26%**;
- all 792 decisions used `unresolved_content_tiebreak`.

The 26.26% score is chance-level behavior, not a claim of scientific reasoning progress. The important verified change is that routing and answer-contract failures are separated from semantic competence, so later reasoning improvements can be measured honestly.

Verification:
- comprehensive GitHub Actions **35590686139 — SUCCESS**;
- Python 3.11: V87.25 focused **6/6**, inherited V87.02-V87.12 text **96/96**, V87.13-V87.24 media/offline **79/79** PASS;
- Python 3.12: the same **181/181** tests PASS;
- GPQA Actions **35590580662 — SUCCESS**.

Anti-gaming boundary:
- no GPQA answer key or benchmark answer table is embedded;
- unresolved forced choices stay confidence 0.25 and internal verdict PARTIAL;
- only independently verified literal arithmetic is marked OK in this stage.

Implementation:
- `fap_benchmark_reasoning.py`
- `fap_v87_25_structured_reasoning_gateway.py`
- `RUN_FAP_V87_25_STRUCTURED_REASONING.cmd`
- `releases/v87_25/structured_reasoning/`
- `benchmarks/sol_gpqa_v8725.py`

V87.24 remains intact underneath this release. Qwen is not used.
