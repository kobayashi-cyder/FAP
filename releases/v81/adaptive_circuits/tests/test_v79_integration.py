from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V79 = RELEASES / "v79" / "creativity_engine"
V78 = RELEASES / "v78" / "learning_integration"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V79))
sys.path.insert(0, str(V78))

from fap_adaptive_circuits import SparseCreativityAdapter, build_v81_responder
from fap_creativity import CreativityEngine


class V79IntegrationTests(unittest.TestCase):
    def test_runtime_executes_only_routed_creativity_circuits(self):
        base = CreativityEngine()
        sparse = SparseCreativityAdapter(base, top_k=2)
        calls = []
        original = base._render

        def traced(operator, task, context):
            calls.append(operator)
            return original(operator, task, context)

        base._render = traced
        items = sparse.generate("低RAMで記憶と仮説探索を組み合わせる", "容量制約", count=5)
        self.assertGreaterEqual(len(items), 1)
        self.assertLessEqual(len(items), 2)
        self.assertEqual(len(calls), len(items))
        self.assertEqual(set(calls), {x.operator for x in items})

    def test_verified_result_updates_v79_and_active_memory(self):
        base = CreativityEngine()
        sparse = SparseCreativityAdapter(base, top_k=2)
        candidate = sparse.generate("省メモリ推論を改善する", "低RAM 制約", count=2)[0]
        exp = sparse.record_verified_result(
            task_id="integration-1",
            task_text="省メモリ推論を改善する",
            candidate=candidate,
            evidence_id="integration-evidence-1",
            reward=0.95,
        )
        self.assertTrue(exp.verified)
        self.assertIn(candidate.operator, sparse.controller.memory.entries)
        self.assertTrue(any(r.get("evidence_id") == "v79:integration-evidence-1" for r in base.experience_store.records))

    def test_v81_composes_with_v78_teacher_learning(self):
        seen = {}

        def base(user_text, context, mode):
            seen["context"] = context
            return "V81-COMPOSED"

        responder = build_v81_responder(base, top_k=2)
        result = responder("エラーを省メモリで直して", "prior", "rich")
        self.assertEqual(result, "V81-COMPOSED")
        self.assertIn("[FAP V81 sparse creativity guidance]", seen["context"])
        self.assertIn("[FAP teacher-learning guidance]", seen["context"])


if __name__ == "__main__":
    unittest.main()
