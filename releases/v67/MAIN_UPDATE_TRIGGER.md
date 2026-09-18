# FAP v67 update trigger

This file is maintained automatically when `main` changes.

- Source branch: `main`
- Source commit: `d6329968a579fa0d20dbdb115a6f7a060d13a68e`
- Commit date: `2026-09-18T07:47:00+09:00`
- Commit message: Add V66 attested production evidence and statistical canary repair loop
- Latest completed release detected on main: `v66`
- Prepared work branch: `listener/v67`

## Changes since the previous processed main state

```
M	FAP_LATEST.md
M	releases/README.md
A	releases/v66/MAIN_UPDATE_TRIGGER.md
A	releases/v66/README_V61.md
A	releases/v66/README_V62.md
A	releases/v66/README_V63.md
A	releases/v66/README_V64.md
A	releases/v66/README_V65.md
A	releases/v66/README_V66.md
A	releases/v66/RELEASE_REPORT_V61.md
A	releases/v66/RELEASE_REPORT_V62.md
A	releases/v66/RELEASE_REPORT_V63.md
A	releases/v66/RELEASE_REPORT_V64.md
A	releases/v66/RELEASE_REPORT_V65.md
A	releases/v66/RELEASE_REPORT_V66.md
A	releases/v66/RUN_V61_FROM_V59_LOG.bat
A	releases/v66/RUN_V62_DEMO.bat
A	releases/v66/RUN_V63_DEMO.bat
A	releases/v66/RUN_V64_DEMO.bat
A	releases/v66/RUN_V64_TESTS.bat
A	releases/v66/RUN_V65_DEMO.bat
A	releases/v66/RUN_V66_DEMO.bat
A	releases/v66/RUN_WINDOWS.bat
A	releases/v66/VERSION.txt
A	releases/v66/benchmarks/dev_results.jsonl
A	releases/v66/benchmarks/holdout_results.jsonl
A	releases/v66/demo_v62_closed_loop.json
A	releases/v66/demo_v63_closed_loop.json
A	releases/v66/demo_v64_runtime_canary.json
A	releases/v66/demo_v65_operational.json
A	releases/v66/demo_v66_operational.json
A	releases/v66/examples/run_v62_demo.py
A	releases/v66/examples/run_v63_demo.py
A	releases/v66/examples/run_v64_demo.py
A	releases/v66/examples/run_v65_demo.py
A	releases/v66/examples/run_v66_demo.py
A	releases/v66/examples/v59_feedback.jsonl
A	releases/v66/examples/v62_artifact.json
A	releases/v66/examples/v62_candidate/skill.py
A	releases/v66/examples/v62_candidate/tests/test_skill.py
A	releases/v66/examples/v62_eval/dev.jsonl
A	releases/v66/examples/v62_eval/evaluator.py
A	releases/v66/examples/v62_eval/holdout.jsonl
A	releases/v66/examples/v62_eval/holdout_1.jsonl
A	releases/v66/examples/v62_eval/holdout_2.jsonl
A	releases/v66/examples/v62_eval/holdout_3.jsonl
A	releases/v66/examples/v62_eval/holdout_4.jsonl
A	releases/v66/examples/v62_eval/holdout_5.jsonl
A	releases/v66/examples/v63_workspace/baseline_candidate/skill.py
A	releases/v66/examples/v63_workspace/candidate_manifest.json
A	releases/v66/examples/v63_workspace/candidates/math_patch/skill.py
A	releases/v66/examples/v63_workspace/candidates/math_patch/tests/test_skill.py
A	releases/v66/examples/v63_workspace/evaluator/dev.jsonl
A	releases/v66/examples/v63_workspace/evaluator/evaluator.py
A	releases/v66/examples/v63_workspace/evaluator/holdout_1.jsonl
A	releases/v66/examples/v63_workspace/evaluator/holdout_2.jsonl
A	releases/v66/examples/v63_workspace/evaluator/holdout_3.jsonl
A	releases/v66/examples/v63_workspace/evaluator/holdout_4.jsonl
A	releases/v66/examples/v63_workspace/evaluator/holdout_5.jsonl
A	releases/v66/fap_autonomy/__init__.py
A	releases/v66/fap_autonomy/ab_observer.py
A	releases/v66/fap_autonomy/activation_manager.py
A	releases/v66/fap_autonomy/android_state_sync.py
A	releases/v66/fap_autonomy/android_v65_sync.py
A	releases/v66/fap_autonomy/attestation.py
A	releases/v66/fap_autonomy/canary_controller.py
A	releases/v66/fap_autonomy/candidate_pipeline.py
A	releases/v66/fap_autonomy/capability_spec.py
A	releases/v66/fap_autonomy/cli.py
A	releases/v66/fap_autonomy/demotion_feedback.py
A	releases/v66/fap_autonomy/evidence_gate.py
A	releases/v66/fap_autonomy/failure_analyzer.py
A	releases/v66/fap_autonomy/holdout_seal.py
A	releases/v66/fap_autonomy/jsonl_benchmark.py
A	releases/v66/fap_autonomy/lifecycle.py
A	releases/v66/fap_autonomy/loop.py
A	releases/v66/fap_autonomy/models.py
A	releases/v66/fap_autonomy/operational_ledger.py
A	releases/v66/fap_autonomy/operational_matrix.py
A	releases/v66/fap_autonomy/post_activation_monitor.py
A	releases/v66/fap_autonomy/priority_engine.py
A	releases/v66/fap_autonomy/production_matrix.py
A	releases/v66/fap_autonomy/promotion_cli.py
A	releases/v66/fap_autonomy/promotion_ledger.py
A	releases/v66/fap_autonomy/provenance.py
A	releases/v66/fap_autonomy/quarantine.py
A	releases/v66/fap_autonomy/quarantine_release.py
A	releases/v66/fap_autonomy/repair_bridge.py
A	releases/v66/fap_autonomy/request_queue.py
A	releases/v66/fap_autonomy/resource_meter.py
A	releases/v66/fap_autonomy/reuse_resolver.py
A	releases/v66/fap_autonomy/runtime_dispatcher.py
A	releases/v66/fap_autonomy/skill_factory_adapter.py
A	releases/v66/fap_autonomy/skill_factory_worker.py
A	releases/v66/fap_autonomy/statistical_canary.py
A	releases/v66/fap_autonomy/telemetry.py
A	releases/v66/fap_autonomy/telemetry_v66.py
A	releases/v66/fap_autonomy/trusted_runner.py
A	releases/v66/fap_autonomy/v59_bridge.py
A	releases/v66/fap_autonomy/v59_operational.py
A	releases/v66/fap_autonomy/v59_operational_cli.py
A	releases/v66/fap_autonomy/v63_cli.py
A	releases/v66/fap_autonomy/v63_closed_loop.py
A	releases/v66/fap_autonomy/v64_coordinator.py
A	releases/v66/fap_autonomy/v65_coordinator.py
A	releases/v66/fap_autonomy/v66_coordinator.py
A	releases/v66/fap_autonomy/verified_registry.py
A	releases/v66/fap_autonomy/verifier.py
A	releases/v66/release_manifest_v61.json
A	releases/v66/release_manifest_v62.json
A	releases/v66/release_manifest_v63.json
A	releases/v66/release_manifest_v64.json
A	releases/v66/release_manifest_v65.json
A	releases/v66/release_manifest_v66.json
A	releases/v66/tests/test_activation_manager.py
A	releases/v66/tests/test_candidate_pipeline.py
A	releases/v66/tests/test_evidence_gate.py
A	releases/v66/tests/test_failure_analyzer.py
A	releases/v66/tests/test_holdout_seal.py
A	releases/v66/tests/test_lifecycle.py
A	releases/v66/tests/test_loop.py
A	releases/v66/tests/test_operational_ledger.py
A	releases/v66/tests/test_post_activation_monitor.py
A	releases/v66/tests/test_priority_engine.py
A	releases/v66/tests/test_promotion_ledger.py
A	releases/v66/tests/test_provenance.py
A	releases/v66/tests/test_request_queue.py
A	releases/v66/tests/test_reuse_resolver.py
A	releases/v66/tests/test_skill_factory_adapter.py
A	releases/v66/tests/test_v59_bridge.py
A	releases/v66/tests/test_v59_operational.py
A	releases/v66/tests/test_v63_closed_loop.py
A	releases/v66/tests/test_v64_runtime_canary.py
A	releases/v66/tests/test_v65_operational.py
A	releases/v66/tests/test_v66_operational.py
A	releases/v66/tests/test_verified_registry.py
A	releases/v66/tests/test_verifier.py
```

## Next-update work contract

1. Inspect the main change and its impact on FAP behavior, tests, packaging, and Android integration.
2. Continue implementation only on `listener/v67` (or another non-main work branch).
3. Add/update tests and release notes under `releases/v67/`.
4. Do not overwrite unrelated existing work in this branch.
5. Merge to `main` only after the update is coherent and verified.
