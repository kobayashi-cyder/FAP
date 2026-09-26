# Public Common Test Benchmark

FAP exposes a public benchmark harness for Japanese Common Test-style evaluation.

## What is public

- benchmark runner and scoring code;
- JSONL input contract;
- per-subject and aggregate score reporting;
- hashes of the question set and answer key;
- a repository-authored synthetic Common-Test-style dataset generator;
- CI that anyone can reproduce.

## Official Common Test questions

The repository does **not** redistribute official Common Test question text.
The National Center for University Entrance Examinations states that secondary
use of its test questions, including use in internet problem collections,
requires a test-question use application. Therefore official questions should
be supplied to the runner only in an evaluation environment where the user has
the necessary rights/permission.

The official adapter uses the same public runner. It requires two JSONL files:

Questions:

```json
{"dataset_id":"official-r8-local","item_id":"math1-001","subject":"mathematics","question":"...","choices":{"A":"...","B":"...","C":"...","D":"..."}}
```

Answer key:

```json
{"item_id":"math1-001","answer":"B"}
```

The report does not reproduce question text or correct-answer text. It records
item IDs, correctness, prediction, verifier verdict, confidence, forced-choice
status, per-subject score, total score, and SHA-256 fingerprints.

## Synthetic public benchmark

Run:

```bash
python benchmarks/common_test_synthetic.py --seed 20260926 --per-subject 4
python benchmarks/common_test_public.py \
  --questions runtime/common_test_synthetic_questions.jsonl \
  --answers runtime/common_test_synthetic_answers.jsonl \
  --output runtime/common_test_report.json
```

The synthetic set is useful for reproducible CI and public regression tracking.
It is **not** a substitute for an actual Common Test score.

## Integrity rule

Runtime FAP code must not receive the answer key. The benchmark harness calls
FAP using question text and choices only, then compares the returned answer
against the evaluator-owned key after inference.
