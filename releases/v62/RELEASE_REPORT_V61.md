# FAP V61 — Operational Capability Discovery Bridge

## Result

V60の自律改善ループを、V59 Adaptive Skill Graphの**検証済み実運用結果**へ接続する層を追加した。

### 実装

- V59 verified outcome -> SQLite operational ledger
- stable turn ID による重複排除
- unverified turn は学習・failure evidenceへ入れない
- deterministic diagnostic / audit 分離
- Evidence Gate
  - verified cases
  - cluster failures
  - family cases
  - failure rate
  - priority score
- Capability reuse resolver
  - 失敗時に既存Skillが繰り返し選択されている場合は `extend_existing_skill`
  - そうでなければ `new_skill_candidate`
- non-executable Capability Spec生成
- atomic Skill Factory request queue
- operational capability matrix
- candidate untouched holdoutとは運用auditを明示的に分離

## Verification

- Python compileall: PASS
- unittest: 25/25 PASS
- request queue: atomic + duplicate safe
- executable payload queueing: rejected
- unverified V59 turn ingestion: rejected from evidence
- repeated verified evidence: Skill Factory request generated
- small-sample evidence: deferred

## Synthetic mechanism demo

入力35行のうち検証済み30行だけを受理。

- diagnostic: 26
- audit: 4
- selected capability: `math_gap__word_problem_quantity_relation_multi_step`
- diagnostic family failure: 9 / 26
- observed failure-time skills: `math` 9/9, `reason` 9/9
- reuse decision: `extend_existing_skill`
- target existing skill: `math`
- Skill Factory request: queued

このデモは**仕組みの検証用合成データ**であり、実FAPの最大弱点が数学だという主張ではない。

## Safety / anti-overfit behavior

1. 未検証turnを捨てる。
2. 少数事例ではSkill Factoryへ進まない。
3. 既存Skillが失敗経路に存在すれば重複Skillより拡張を優先する。
4. queueに入るのは実行コードではなく要求仕様のみ。
5. generated candidateは従来どおりstatic gate / sandbox / dev benchmark / untouched holdout / repeated verified successを通す必要がある。
6. operational audit bucketをcandidate holdoutと混同しない。

## Next integration point

実V59で1turnごとに以下をJSONLへ出せば接続できる。

- `turn_id`
- `text`
- `intent`
- `domain`
- `selected_skills`
- `verified` + `verified_success` または検証済み `verify_feedback=good|bad`
- `teacher_used`
- `latency_ms`
- optional: `error`, `critic_ok`, `topic`, `metadata.gap_path`

実行:

```bat
RUN_V61_FROM_V59_LOG.bat C:\path\to\v59_verified_log.jsonl
```

出力された `skill_factory_inbox/*.json` を既存Skill Factoryへ渡す。
