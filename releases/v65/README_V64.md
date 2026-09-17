# FAP V64 — Verified Runtime Dispatch + Canary A/B

V63のverified activation / rollback control planeを、runtime dispatchとcanary評価へ接続する累積リリースです。

## V64で追加したもの

- load時にactive slotのdigestを再計算して照合
- symlinkを含むslotをruntime dispatch前に拒否
- request IDのSHA-256による決定論的canary routing
- verified slotだけを外部のtrusted OS/container runnerへ渡す`SandboxedRuntimeBridge`
- baseline/activeのverified-only A/B observation
- success / quality / p95 latencyのregression gate
- rollback成功後だけcandidateをdemotedとしてFailure Memoryへ返す
- Android向けactive-state export（hostのslot pathは除去）

## 安全境界

V64自身は未知candidate Pythonをimportしません。`SandboxedRuntimeBridge`もOS/container sandboxそのものではなく、既存のtrusted runnerへ**digest検証済みslotだけ**を渡す契約です。slot改変・symlink・manifest不整合時にはrunnerを呼びません。

## 検証

- V63 main baseline: 63/63 PASS（V63 releaseで検証済み）
- V64追加テスト: **19/19 PASS**
- V64 compileall: PASS
- warnings-as-errors: PASS
- synthetic canary A/B → rollback → demotion/Failure Memory demo: PASS
  - baseline success 1.0 / active success 0.5
  - quality delta -0.32
  - p95 latency ratio 2.4x
  - rollback triggered
  - Failure Memory written
  - Android exportにslot pathなし

同梱demoは機構検証用であり、公開benchmark scoreやSol相当性能を示すものではありません。
