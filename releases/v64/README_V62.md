# FAP V62 — Verified Candidate Promotion Loop

V61の「実運用失敗 → 能力要求書」へ、候補能力の検証・昇格側を追加する累積パッチです。

## V62で追加した閉ループ

```text
verified failure cluster
        ↓
Skill Factory candidate
        ↓
static safety gate
        ↓
unit test
        ↓
sandbox/process execution
        ↓
development benchmark
        ↓
sealed untouched holdout
        ↓
resource gate
        ↓
unique evidence ledger
        ↓
ephemeral → shadow → consolidated
        ↓
verified registry manifest
```

## 重要な安全条件

- 候補Pythonは静的安全ゲートを先に通す。
- holdoutファイルは実行前後のSHA-256を照合する。
- 同じ `trial_id` は再加算しない。
- `trial_id`だけ変えても、同じcandidate + 同じholdout evidenceなら再加算しない。
- candidateのバイト列が変わればdigestが変わり、lifecycleを新しく開始する。
- RAMは可能なら子プロセスのpeak RSSを実測する。
- resource gate / dev / holdout / regression条件を満たさない候補は成功trialにならない。
- 5つ以上の異なるverified evidence、success rate >= 0.8、confidence >= 0.68等を満たしたときのみconsolidated。
- Registry登録はmanifestのみ。未知コードを自動import/activateしない。

## 検証

- Python compileall: PASS
- unittest: **42/42 PASS**
- ResourceWarningをerror扱いしてPASS
- 実subprocess integration test: PASS
- synthetic 5-shard closed-loop demo: PASS
  - trial 1: ephemeral
  - trial 2-4: shadow
  - trial 5: consolidated + registry manifest
- demo peak RSS: 約91 MB（この検証環境のPython子プロセス。FAP本体のRAM値ではない）

## 実行

全テスト:

```bash
python -m unittest discover -s tests -v
```

V62合成閉ループデモ:

```bash
python examples/run_v62_demo.py
```

Windows:

```bat
RUN_V62_DEMO.bat
```

## 現時点の境界

`CommandRunner` はtimeout・peak RSS計測を行いますが、OSレベルの完全なセキュリティサンドボックスそのものではありません。
本番統合時は既存FAP Skill Factoryのcontainer/OS sandbox bridgeへ置換してください。

また、同梱デモはpipeline検証用の小さな数学fixtureです。公開ベンチマークや実FAP能力の改善値ではありません。
