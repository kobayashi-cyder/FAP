from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fap_autonomy.activation_manager import ActivationManager
from fap_autonomy.candidate_pipeline import CandidatePromotionPipeline
from fap_autonomy.post_activation_monitor import PostActivationMonitor
from fap_autonomy.promotion_ledger import PromotionLedger, digest_tree
from fap_autonomy.provenance import ProvenanceLedger
from fap_autonomy.skill_factory_adapter import SkillFactoryOutputAdapter
from fap_autonomy.v63_closed_loop import V63ClosedLoopCoordinator
from fap_autonomy.verified_registry import VerifiedSkillRegistry

WS = ROOT / "examples" / "v63_workspace"
STATE = ROOT / "demo_v63_state"
if STATE.exists():
    shutil.rmtree(STATE)
STATE.mkdir()

registry = VerifiedSkillRegistry(str(STATE / "verified_registry.json"))
ledger = PromotionLedger(str(STATE / "promotion.sqlite3"))
prov = ProvenanceLedger(str(STATE / "activation" / "provenance.jsonl"))
activation = ActivationManager(str(STATE / "activation"), provenance=prov)

base_dir = WS / "baseline_candidate"
base_digest = digest_tree(str(base_dir))
base_entry = {
    "capability_id": "MATH_GAP:word_problem_quantity_relation_multi_step",
    "candidate_digest": base_digest,
    "candidate_dir": str(base_dir),
    "evidence": {"candidate_digest": base_digest, "lifecycle": {"state": "consolidated"},
                 "latest_evidence": {"holdout": {"score": 0.80}}},
}
activation.activate_from_registry(base_entry, baseline_quality=.80, baseline_latency_ms=100.0)

adapter = SkillFactoryOutputAdapter(candidate_root=str(WS / "candidates"), evaluator_root=str(WS / "evaluator"))
pipeline = CandidatePromotionPipeline(ledger=ledger, registry=registry)
coord = V63ClosedLoopCoordinator(adapter=adapter, pipeline=pipeline, registry=registry, activation=activation)
promotion = coord.process_manifest(str(WS / "candidate_manifest.json"), baseline_dev_score=.70,
                                   min_dev_gain=.10, min_holdout_score=.80)

active_after_promotion = activation.current("MATH_GAP:word_problem_quantity_relation_multi_step")
monitor = PostActivationMonitor(str(STATE / "runtime.sqlite3"), activation, min_samples=12, window=12)
for i in range(12):
    monitor.ingest(event_id=f"prod-{i}", capability_id="MATH_GAP:word_problem_quantity_relation_multi_step",
                   verified=True, success=(i < 6), quality=.55, latency_ms=230.0,
                   evidence={"synthetic_demo": True})
post = monitor.evaluate("MATH_GAP:word_problem_quantity_relation_multi_step")
active_after_monitor = activation.current("MATH_GAP:word_problem_quantity_relation_multi_step")

result = {
    "synthetic_demo": True,
    "promotion_status": promotion["status"],
    "promotion_states": [(x.get("lifecycle") or {}).get("state") for x in promotion["trials"]],
    "activated_digest": (active_after_promotion or {}).get("candidate_digest"),
    "baseline_digest": base_digest,
    "post_activation_status": post["status"],
    "rollback_restored_baseline": (active_after_monitor or {}).get("candidate_digest") == base_digest,
    "provenance": prov.verify(),
}
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
(ROOT / "demo_v63_closed_loop.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
