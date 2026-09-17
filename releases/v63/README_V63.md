# FAP V63 — Activation, Monitoring and Automatic Rollback

V62の verified candidate promotion を、実運用activationとrollbackまで接続する累積リリース。

## 閉ループ

verified failure → Skill Factory output manifest → V62 evaluator → consolidated registry → atomic active-manifest switch → verified runtime monitoring → regression detection → automatic rollback

## V63で追加

- `SkillFactoryOutputAdapter`: candidate output manifestを検証し、candidateコードをimportしない。
- `SkillFactoryCommandBridge`: 既存の信頼済みSkill Factoryプロセスを呼ぶbridge。生成物はV62 evaluatorへ送る。
- `AtomicActivationManager`: active manifestの原子的切替、candidate digest再検証、previous activation保存、rollback時のprevious digest再検証。
- `PostActivationMonitor`: verified outcomeだけを取り込み、event_id重複排除、最小サンプル数gate、success-rate低下とlatency悪化を監視。
- `PatchHistory`: candidate evaluation / activation / rollback provenanceをappend-only JSONLへ記録。
- `V63Orchestrator`: V62 pipeline → registry → activation → monitor → rollbackを接続。

## 検証

- compileall: PASS
- V62継承42テスト + V63追加15テスト = **57/57 PASS**
- warnings as errors: PASS
- activation/rollback synthetic integration demo: PASS
  - verified runtime case 6件
  - success rate 0.333 vs baseline 0.900
  - latency ratio 2.25x
  - success + latency regressionを検出
  - old candidate digestへrollback一致

## 重要

V63のactivationは安全側の**manifest pointer切替**であり、生成Pythonをこの層が直接importして実行する仕組みではない。実ランタイムはactive manifestを既存FAP runtime/skill registry bridgeで解決する。

同梱デモは仕組みの検証用合成データであり、FAP実性能や公開ベンチマーク結果ではない。
