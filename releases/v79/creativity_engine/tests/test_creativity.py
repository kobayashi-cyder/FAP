from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V78 = RELEASES / "v78" / "learning_integration"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V78))

from fap_creativity import (
    CreativeCandidate,
    CreativeExperienceStore,
    CreativityAugmentedResponder,
    CreativityEngine,
    OPERATORS,
    build_v79_responder,
)


class CreativityTests(unittest.TestCase):
    def test_generates_diverse_operator_candidates(self):
        engine = CreativityEngine()
        items = engine.generate("低RAMで会話能力を高める", "16GB以内", count=5)
        self.assertEqual(len(items), 5)
        self.assertEqual({x.operator for x in items}, set(OPERATORS))
        self.assertTrue(all(x.score >= 0.0 for x in items))
        self.assertTrue(all(x.text for x in items))

    def test_bundled_success_experience_is_absorbed(self):
        engine = CreativityEngine()
        self.assertEqual(set(engine.experience_store.consolidated_operators()), set(OPERATORS))
        verified = [r for r in engine.experience_store.records if r.get("verified") is True]
        self.assertEqual(len(verified), 15)
        self.assertTrue(all(r.get("stage") in {"ephemeral", "shadow", "consolidated"} for r in verified))

    def test_bundled_experience_can_be_disabled_for_clean_evaluation(self):
        engine = CreativityEngine(use_bundled_experience=False)
        self.assertEqual(engine.experience_store.records, [])
        self.assertEqual(engine.experience_store.consolidated_operators(), [])

    def test_recombine_uses_multiple_winning_ideas(self):
        engine = CreativityEngine()
        items = engine.generate("新しい学習方法を考える", count=3)
        merged = engine.recombine(items, top_k=2)
        self.assertIn("再結合[", merged)
        self.assertIn(items[0].operator, merged)
        self.assertIn(items[1].operator, merged)

    def test_verified_success_promotes_ephemeral_shadow_consolidated(self):
        with tempfile.TemporaryDirectory() as td:
            store = CreativeExperienceStore(Path(td) / "creative.json")
            engine = CreativityEngine(store)
            task = "小型AIの発想を増やす"
            candidate = engine.generate(task, count=5)[0]
            stages = []
            for i in range(3):
                exp = engine.verified_success(
                    task_id=f"task-{i}",
                    task_text=task,
                    candidate=candidate,
                    evidence_id=f"evidence-{i}",
                    reward=0.90,
                )
                stages.append(exp.stage)
            self.assertEqual(stages, ["ephemeral", "shadow", "consolidated"])
            self.assertIn(candidate.operator, store.consolidated_operators())

    def test_duplicate_evidence_cannot_fake_consolidation(self):
        store = CreativeExperienceStore()
        engine = CreativityEngine(store)
        task = "再利用可能な発想を作る"
        candidate = engine.generate(task, count=1)[0]
        engine.verified_success(
            task_id="a", task_text=task, candidate=candidate, evidence_id="same", reward=0.95
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            engine.verified_success(
                task_id="b", task_text=task, candidate=candidate, evidence_id="same", reward=0.95
            )
        self.assertEqual(store.consolidated_operators(), [])

    def test_failed_or_unverified_experience_is_not_absorbed(self):
        store = CreativeExperienceStore()
        engine = CreativityEngine(store)
        task = "安全な創造性"
        candidate = engine.generate(task, count=1)[0]
        rejected = store.observe(
            task_id="bad",
            task_text=task,
            candidate=candidate,
            evidence_id="bad-1",
            reward=0.99,
            verified=False,
        )
        weak = store.observe(
            task_id="weak",
            task_text=task,
            candidate=candidate,
            evidence_id="bad-2",
            reward=0.20,
            verified=True,
        )
        self.assertEqual(rejected.stage, "rejected")
        self.assertEqual(weak.stage, "rejected")
        self.assertEqual(store.operator_weights(task)[candidate.operator], 1.0)

    def test_successful_operator_gets_priority_on_future_generation(self):
        store = CreativeExperienceStore()
        engine = CreativityEngine(store)
        task = "省メモリで新しい会話機構"
        base = engine.generate(task, count=5)
        winner = next(x for x in base if x.operator == "inversion")
        for i in range(3):
            engine.verified_success(
                task_id=f"inv-{i}",
                task_text=task,
                candidate=winner,
                evidence_id=f"inv-evidence-{i}",
                reward=1.0,
            )
        later = engine.generate(task, count=5)
        self.assertEqual(later[0].operator, "inversion")

    def test_persistence_keeps_absorbed_success(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "creative.json"
            store = CreativeExperienceStore(path)
            engine = CreativityEngine(store)
            task = "創造経験の永続化"
            candidate = next(
                x for x in engine.generate(task, count=5)
                if x.operator == "combination"
            )
            for i in range(3):
                engine.verified_success(
                    task_id=f"persist-{i}",
                    task_text=task,
                    candidate=candidate,
                    evidence_id=f"persist-evidence-{i}",
                    reward=0.9,
                )
            restored = CreativeExperienceStore(path)
            self.assertIn("combination", restored.consolidated_operators())
            self.assertGreater(restored.operator_weights(task)["combination"], 1.0)

    def test_mechanism_verifier_rejects_low_quality_candidate(self):
        engine = CreativityEngine(use_bundled_experience=False)
        bad = CreativeCandidate(
            text="x",
            operator="analogy",
            novelty=0.1,
            utility=0.1,
            consistency=0.1,
            diversity=0.1,
            score=0.1,
        )
        verified, reward = engine.verify_candidate("創造課題", bad)
        self.assertFalse(verified)
        self.assertLess(reward, 0.70)

    def test_wrapper_keeps_base_responder_in_control_and_labels_ideas(self):
        seen = {}

        def base(user_text, context, mode):
            seen["context"] = context
            return "BASE"

        wrapped = CreativityAugmentedResponder(base)
        result = wrapped("新しい仕組みを考えて", "prior", "rich")
        self.assertEqual(result, "BASE")
        self.assertIn("[FAP creativity guidance]", seen["context"])
        self.assertIn("not facts", seen["context"])

    def test_v79_composes_with_v78_distilled_guidance(self):
        seen = {}

        def base(user_text, context, mode):
            seen["context"] = context
            return "COMPOSED"

        responder = build_v79_responder(base)
        result = responder("エラーを新しい方法で修正して", "prior", "rich")
        self.assertEqual(result, "COMPOSED")
        self.assertIn("[FAP creativity guidance]", seen["context"])
        self.assertIn("[FAP teacher-learning guidance]", seen["context"])
        self.assertIn("debugging", seen["context"])


if __name__ == "__main__":
    unittest.main()
