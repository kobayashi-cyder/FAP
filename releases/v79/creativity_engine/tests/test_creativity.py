from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity import (
    CreativeCandidate,
    CreativeExperienceStore,
    CreativityAugmentedResponder,
    CreativityEngine,
    OPERATORS,
)


class CreativityTests(unittest.TestCase):
    def test_generates_diverse_operator_candidates(self):
        engine = CreativityEngine()
        items = engine.generate("低RAMで会話能力を高める", "16GB以内", count=5)
        self.assertEqual(len(items), 5)
        self.assertEqual({x.operator for x in items}, set(OPERATORS))
        self.assertTrue(all(x.score >= 0.0 for x in items))
        self.assertTrue(all(x.text for x in items))

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
            candidate = engine.generate("小型AIの発想を増やす", count=5)[0]
            stages = []
            for i in range(3):
                exp = engine.verified_success(
                    task_id=f"task-{i}",
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
        candidate = engine.generate("再利用可能な発想を作る", count=1)[0]
        engine.verified_success(
            task_id="a", candidate=candidate, evidence_id="same", reward=0.95
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            engine.verified_success(
                task_id="b", candidate=candidate, evidence_id="same", reward=0.95
            )
        self.assertEqual(store.consolidated_operators(), [])

    def test_failed_or_unverified_experience_is_not_absorbed(self):
        store = CreativeExperienceStore()
        engine = CreativityEngine(store)
        candidate = engine.generate("安全な創造性", count=1)[0]
        rejected = store.observe(
            task_id="bad",
            candidate=candidate,
            evidence_id="bad-1",
            reward=0.99,
            verified=False,
        )
        weak = store.observe(
            task_id="weak",
            candidate=candidate,
            evidence_id="bad-2",
            reward=0.20,
            verified=True,
        )
        self.assertEqual(rejected.stage, "rejected")
        self.assertEqual(weak.stage, "rejected")
        self.assertEqual(store.operator_weights()[candidate.operator], 1.0)

    def test_successful_operator_gets_priority_on_future_generation(self):
        store = CreativeExperienceStore()
        engine = CreativityEngine(store)
        base = engine.generate("省メモリで新しい会話機構", count=5)
        winner = next(x for x in base if x.operator == "inversion")
        for i in range(3):
            engine.verified_success(
                task_id=f"inv-{i}",
                candidate=winner,
                evidence_id=f"inv-evidence-{i}",
                reward=1.0,
            )
        later = engine.generate("省メモリで新しい会話機構", count=5)
        self.assertEqual(later[0].operator, "inversion")

    def test_persistence_keeps_absorbed_success(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "creative.json"
            store = CreativeExperienceStore(path)
            engine = CreativityEngine(store)
            candidate = next(
                x for x in engine.generate("創造経験の永続化", count=5)
                if x.operator == "combination"
            )
            for i in range(3):
                engine.verified_success(
                    task_id=f"persist-{i}",
                    candidate=candidate,
                    evidence_id=f"persist-evidence-{i}",
                    reward=0.9,
                )
            restored = CreativeExperienceStore(path)
            self.assertIn("combination", restored.consolidated_operators())
            self.assertGreater(restored.operator_weights()["combination"], 1.0)

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


if __name__ == "__main__":
    unittest.main()
