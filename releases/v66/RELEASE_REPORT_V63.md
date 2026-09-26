# FAP V63 Release Report

## Objective

V62でconsolidatedになったcandidateを「登録しただけ」で終わらせず、既存Skill Factory outputから安全に受け取り、検証済みsnapshotとしてactive pointerへ昇格し、稼働後の検証済み観測で悪化した場合に直前のverified digestへ戻せるcontrol planeを構築する。

## Implemented

### 1. SkillFactoryOutputAdapter

candidate rootとevaluator rootを分離し、manifestを正規化する。

- path traversal拒否
- evaluator-owned holdout必須
- candidate tree内holdout拒否
- argv listのみ
- shell interpreter拒否
- `python -c`拒否
- `-m`実行はunit-test用`unittest`のみに限定
- evaluator scriptはevaluator root内の既存`.py`のみ

### 2. ActivationManager

verified registry entryの`lifecycle.state == consolidated`だけをactivation対象とする。

- source digest照合
- symlink拒否
- managed slotへcopy
- copy後digest再照合
- atomic active pointer
- previous verified pointer history
- rollback前にprevious slot digest再検証
- code import/activationは行わない

### 3. PostActivationMonitor

- verified observationのみ永続化
- event ID duplicate排除
- active candidate digestごとにwindowを分離
- minimum evidence gate
- quality regression
- success-rate regression
- p95 latency regression
- regression時にActivationManager rollback

### 4. ProvenanceLedger

activation系操作をhash chainで記録するtamper-evident ledgerを追加。
既存chainが壊れている場合は新規event追記を拒否する。

### 5. V63ClosedLoopCoordinator

既存Skill Factory candidate manifestをV62 CandidatePromotionPipelineへ渡し、consolidatedになったcandidateだけをVerifiedSkillRegistryからActivationManagerへ接続する。

## Validation

- compileall: PASS
- unittest: **63/63 PASS**
- ResourceWarning-as-error: PASS
- synthetic real-subprocess closed-loop: PASS

統合demo結果:

```text
promotion states:
  ephemeral
  shadow
  shadow
  shadow
  consolidated
promotion status: activated
post activation status: rollback_triggered
rollback restored baseline: true
provenance chain: valid
```

## Safety fixes found during review

初期実装後のレビューで以下を追加修正した。

1. candidate treeのsymlinkを拒否。
2. candidate manifestの`python -c`を拒否。
3. rollback先slotをdigest再検証し、改変済みならrollbackしない。
4. provenance chainが改変済みなら追記を拒否。
5. quality / latency baselineの範囲検証を追加。

修正後に全テストと統合demoを再実行した。

## Remaining limitations

- activationはcontrol-plane pointer switchであり、未知codeをFAP runtimeへ直接importしない。
- runtime dispatcher / container loaderがactive pointerを読む接続は次段。
- production observationのqualityはactivation baselineと同じ0..1 verifier尺度である必要がある。
- synthetic demoであり、実FAPの性能改善率を意味しない。

## Next target — V64

1. sandboxed runtime dispatcher bridge
2. active manifestのdigest verification at load time
3. capability routing → active verified skill slot
4. canary activation (部分トラフィック)
5. baseline/active A-B observation
6. rollback後candidate demotion + Failure Memory feedback
7. Android packaging側へのactive-registry state同期
