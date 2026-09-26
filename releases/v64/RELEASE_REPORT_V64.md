# FAP V64 Release Report

## Objective
V63のatomic active pointerを、実行直前のintegrity verification、canary traffic、baseline-vs-active観測、rollback後のdemotion feedbackまで接続する。

## Implemented
1. ActiveRuntimeDispatcher — active manifest読込、slot/digest/symlink検証。
2. SandboxedRuntimeBridge — 検証済みslotのみtrusted runnerへ渡す。candidate codeは直接importしない。
3. Deterministic canary routing — request_id SHA-256 bucket。
4. ABObserver — verified-only、duplicate排除、minimum evidence、success/quality/p95 latency比較。
5. V64Coordinator — A/B regression時のV63 rollback接続。
6. DemotionFeedback — rollback成功candidateをdemotion historyとFailure Memoryへ戻す。
7. AndroidStateSync — atomic sanitised active-state export。host slot pathを含めない。

## Review fix
統合demoで、rollback evidence辞書とdemotion結果が同じ参照を共有して循環参照になり得る問題を発見。Failure Memoryへ渡すevidenceをdeep-copy snapshotに変更し、JSON serialization regression testを追加した。

## Validation
- V64 delta unittest: 19/19 PASS
- compileall: PASS
- warnings-as-errors: PASS
- synthetic integrated demo: PASS

V63の既存63 testsはreleases/v64/testsへtree継承し、V64 testを追加している。ここで報告する19/19は今回実際に再実行したV64差分テスト数であり、未実行の合計82/82という主張はしない。

## Next target — V65
1. real Skill Factory inbox/outbox watcher bridge
2. trusted sandbox runner adapter implementation
3. runtime verified telemetry ingestion from actual FAP dispatcher
4. canary ratio auto-ramp 5%→20%→50%→100%
5. healthy active candidate promotion confirmation
6. repeated rollback candidate quarantine
7. benchmark-driven next-capability selection with real non-synthetic tasks
