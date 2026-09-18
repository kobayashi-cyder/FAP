# FAP V63 — Verified Activation + Post-Activation Rollback

V62の「候補Skillを sealed holdout で検証し consolidated まで昇格する」仕組みに、
**Skill Factory出力の受け入れ、検証済みsnapshotのactivation control plane、稼働後regression監視、自動rollback**を追加する累積リリースです。

## V63で追加した閉ループ

```text
verified failure cluster
        ↓
Skill Factory request
        ↓
existing Skill Factory candidate manifest
        ↓
V63 manifest/path/command validation
        ↓
V62 static safety + unit + dev + sealed holdout + resource gate
        ↓
unique verified evidence
        ↓
ephemeral → shadow → consolidated
        ↓
verified registry
        ↓
immutable-by-digest managed snapshot
        ↓
atomic active pointer switch
        ↓
verified production observations
        ↓
windowed regression decision
        ↓
healthy → keep active
regression → rollback to previous verified digest
```

## 新規モジュール

- `fap_autonomy/skill_factory_adapter.py`
  - 既存Skill Factoryが出力するcandidate manifestを検証
  - candidate/evaluator root外へのpath escapeを拒否
  - holdoutはcandidate tree外のevaluator-owned fileだけ許可
  - shell commandと`python -c`を拒否
- `fap_autonomy/activation_manager.py`
  - consolidated entryだけsnapshot化
  - candidate digestをcopy前後で照合
  - symlinkを拒否
  - atomic `active.json` pointer switch
  - rollback先slotもdigest再検証
  - candidate code自体はimport/executeしない
- `fap_autonomy/post_activation_monitor.py`
  - verified runtime observationだけを採用
  - duplicate eventを排除
  - 最小sample数まではrollbackしない
  - quality / success-rate / latency regressionを監視
- `fap_autonomy/provenance.py`
  - activation / rollback履歴のhash chain
  - 改変済みchainには追記しない
- `fap_autonomy/v63_closed_loop.py`
  - Skill Factory manifest → V62 verifier → consolidated → activationを接続

## Validation

- Python compileall: PASS
- unittest: **63/63 PASS**
- `ResourceWarning`をerror扱いしたテスト: PASS
- 強化後のsynthetic end-to-end demo: PASS
  - promotion: `ephemeral → shadow → shadow → shadow → consolidated`
  - activation: PASS
  - verified production regression observations: 12
  - rollback: triggered
  - previous verified digest restored: PASS
  - provenance hash chain: valid

## 実行

```bash
python -m unittest discover -s tests -v
python examples/run_v63_demo.py
```

Windows:

```bat
RUN_V63_DEMO.bat
```

## 重要な境界

V63のactivationは**安全なcontrol-plane pointer switch**です。candidate codeを未知のまま自動importしてFAPプロセスへ注入しません。
FAP実行時dispatcherが`active.json`を読み、既存のOS/container sandbox境界でそのslotをロードするruntime bridgeは次段です。

同梱demoは閉ループ機構のsynthetic fixtureであり、公開benchmark scoreやGPT-5.6 Sol相当性能を示すものではありません。
