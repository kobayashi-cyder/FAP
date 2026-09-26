import json
import os
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.activation_manager import ActivationManager
from fap_autonomy.promotion_ledger import digest_tree
from fap_autonomy.skill_factory_adapter import SkillFactoryOutputAdapter
from fap_autonomy.v63_closed_loop import V63ClosedLoopCoordinator
from fap_autonomy.verified_registry import VerifiedSkillRegistry


def workspace(d, trials=5):
    root = Path(d); croot = root / "candidates"; eroot = root / "eval"
    cand = croot / "c1"; cand.mkdir(parents=True); eroot.mkdir()
    (cand / "skill.py").write_text("def solve(x): return x\n", encoding="utf-8")
    (eroot / "evaluator.py").write_text("print('{\"score\":1.0,\"cases\":1,\"passed\":1}')\n", encoding="utf-8")
    for i in range(trials):
        (eroot / f"h{i}.jsonl").write_text(f"{{\"i\":{i}}}\n", encoding="utf-8")
    manifest = {
        "schema": 1, "request_id": "r1", "capability_id": "cap",
        "candidate_relpath": "c1", "evaluator_relpath": ".",
        "unit_command": ["{python}", "-m", "unittest", "discover"],
        "dev_command": ["{python}", "evaluator.py"],
        "trials": [{"trial_id": f"t{i}", "holdout_paths": [f"h{i}.jsonl"],
                    "holdout_command": ["{python}", "evaluator.py"]} for i in range(trials)],
        "production_baseline_latency_ms": 100,
    }
    mp = root / "candidate_manifest.json"; mp.write_text(json.dumps(manifest), encoding="utf-8")
    return croot, eroot, cand, mp


class FakePromotionPipeline:
    def __init__(self, registry, consolidate_at=5):
        self.registry = registry; self.calls = 0; self.consolidate_at = consolidate_at

    def evaluate_once(self, *, capability_id, artifact, trial_id, baseline_dev_score, min_dev_gain, min_holdout_score):
        self.calls += 1
        digest = digest_tree(artifact["candidate_dir"])
        state = "consolidated" if self.calls >= self.consolidate_at else ("shadow" if self.calls >= 2 else "ephemeral")
        evidence = {"holdout": {"score": .95}}
        if state == "consolidated":
            self.registry.register_verified(capability_id, artifact,
                {"candidate_digest": digest, "lifecycle": {"state": "consolidated"}, "latest_evidence": evidence})
        return {"candidate_digest": digest, "lifecycle": {"state": state}, "success": True,
                "evidence": evidence, "status": "candidate_evaluated"}


class V63ClosedLoopTests(unittest.TestCase):
    def test_consolidated_candidate_is_staged_and_activated(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot, cand, mp = workspace(d, 5)
            registry = VerifiedSkillRegistry(os.path.join(d, "registry.json"))
            pipeline = FakePromotionPipeline(registry, consolidate_at=5)
            activation = ActivationManager(os.path.join(d, "activation"))
            coord = V63ClosedLoopCoordinator(
                adapter=SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot)),
                pipeline=pipeline, registry=registry, activation=activation)
            out = coord.process_manifest(str(mp), baseline_dev_score=.5)
            self.assertEqual(out["status"], "activated")
            self.assertEqual(pipeline.calls, 5)
            self.assertEqual(activation.current("cap")["candidate_digest"], digest_tree(str(cand)))

    def test_non_consolidated_candidate_not_activated(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot, cand, mp = workspace(d, 2)
            registry = VerifiedSkillRegistry(os.path.join(d, "registry.json"))
            pipeline = FakePromotionPipeline(registry, consolidate_at=5)
            activation = ActivationManager(os.path.join(d, "activation"))
            coord = V63ClosedLoopCoordinator(
                adapter=SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot)),
                pipeline=pipeline, registry=registry, activation=activation)
            out = coord.process_manifest(str(mp), baseline_dev_score=.5)
            self.assertEqual(out["status"], "not_consolidated")
            self.assertIsNone(activation.current("cap"))


if __name__ == "__main__":
    unittest.main()
