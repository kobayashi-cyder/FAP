# FAP V61 — Operational Capability Discovery Bridge

V60の自律能力改善ループを、V59 Adaptive Skill Graphの**検証済み実運用結果**へ接続する追加パッチです。

## 追加したもの

- V59 verified outcome の永続SQLite ledger（重複投入は無害）
- 未検証turnの完全除外
- deterministic audit bucket（能力選定には使わない）
- Evidence Gate
  - 少数事例だけではSkill Factoryへ進まない
  - verified件数 / cluster失敗数 / family件数 / failure rate / priority score を要求
- Capability Spec Builder
  - 実行コードではなく、既存Skill Factoryへ渡す要求仕様を生成
  - unit / regression / dev / untouched holdout / resource measurement をacceptance条件に含む
- `RUN_V61_FROM_V59_LOG.bat`

## 実運用

```bat
RUN_V61_FROM_V59_LOG.bat C:\path\to\v59_verified_log.jsonl
```

または:

```bash
python -m fap_autonomy.v59_operational_cli v59_verified_log.jsonl \
  --state fap_v61_operational.sqlite3 \
  --out reports/v61_capability_decision.json
```

## 重要

`audit` bucket はcandidate評価用holdoutではありません。能力選定から一部運用データを隔離するだけです。
Skill候補を実装した後の **untouched holdout benchmark** は、既存Benchmark/Skill Factory側で別途必須です。

このpatchは未知生成コードをimportしません。`skill_factory_request` は non-executable specification です。
