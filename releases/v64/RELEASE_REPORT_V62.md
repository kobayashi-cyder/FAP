# FAP V62 Release Report

## Objective

V61で生成されるSkill Factory要求を受けた後、候補能力を無検証で定着させず、静的検査・実行テスト・development benchmark・untouched holdout・資源制約・反復検証を経てverified registryへ昇格できる最小閉ループを作る。

## Implemented

### 1. CandidatePromotionPipeline
`fap_autonomy/candidate_pipeline.py`

- candidate tree static safety inspection
- unit test execution
- development benchmark execution
- holdout benchmark execution
- benchmark JSON result validation (`0 <= passed <= cases`を含む)
- holdout integrity verification
- peak RSS measurement (psutil available時)
- code/disk/test-time/RAM budget gate
- baseline regression check
- duplicate evidence rejection

### 2. HoldoutSeal
`fap_autonomy/holdout_seal.py`

Evaluator所有のholdout bytesをSHA-256で封印し、評価後に変更がないことを確認する。Evidence hashはpathではなくcontent digestを基礎にするため、同一内容を別pathへ複製しても新しいevidence扱いにならない。

### 3. PromotionLedger
`fap_autonomy/promotion_ledger.py`

SQLiteで trial_id / capability_id / candidate_digest / success / confidence / dev / holdout / regression / resource gate / holdout hash / evidence_key を永続化する。

`trial_id`重複、および同一 capability + candidate digest + evidence key の重複を加算しない。

### 4. VerifiedSkillRegistry
`fap_autonomy/verified_registry.py`

`consolidated`以外は登録拒否。登録はatomic JSON manifestであり、candidate codeをimport/activateしない。

## Validation

- Python compileall: PASS
- unittest: **42/42 PASS**
- ResourceWarningを例外化した状態でもPASS
- 実subprocess integration: PASS

Synthetic 5-shard demonstration:

| trial | dev | holdout | lifecycle | registry |
|---|---:|---:|---|---|
| 1 | 1.0 | 1.0 | ephemeral | no |
| 2 | 1.0 | 1.0 | shadow | no |
| 3 | 1.0 | 1.0 | shadow | no |
| 4 | 1.0 | 1.0 | shadow | no |
| 5 | 1.0 | 1.0 | consolidated | yes |

Peak RSSは各trial約91MB。これは本検証環境のPythonプロセス値でありFAP本体のRAM値ではない。

## Fixed during review

SQLite connection cleanupを厳格化した際に露呈したtransaction commit欠落を、autocommit + explicit closeへ修正した。

また、単なる一意trial IDだけでは同じholdoutの再実行を何度も昇格証拠にできたため、content-based `evidence_key` を追加。同じcandidateと同じholdout evidenceはtrial IDを変更しても再加算しない。

最終レビューではbenchmark出力の `passed > cases` を拒否する境界テストも追加した。

## Remaining limitations

- OS/container isolationは既存FAP sandboxへ接続する必要がある。
- demo benchmarkはsyntheticであり、GSM8K等の公式スコアではない。
- registry manifest登録後のproduction activation/rollback bridgeは次段。
- candidateを生成・修復するSkill Factory本体の自律反復は次段。

## Next target — V63

1. Existing Skill Factory candidate output adapter
2. failure → candidate generation → V62 evaluatorの自動接続
3. consolidated candidate activation bridge
4. post-activation regression monitor
5. regression時のautomatic rollback
6. patch history / provenance
