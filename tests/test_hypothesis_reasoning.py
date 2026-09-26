from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_hypothesis_engine import HypothesisEngine
from fap_v87_52_hypothesis_reasoning_gateway import FAPV8752Unified


class HypothesisReasoningTests(unittest.TestCase):
    def test_competing_hypotheses_include_predictions_and_falsifiers(self):
        core = FAPV8752Unified()
        out = core.chat(
            "大気の運動について競合仮説と反証条件を出して",
            "v8752-atmosphere-hypotheses",
        )
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("hypothesis-generate", out["route"])
        self.assertIn("falsification-plan", out["route"])
        meta = out["hypothesis_reasoning"]
        self.assertTrue(meta["enabled"])
        self.assertGreaterEqual(meta["generated"], 5)
        self.assertFalse(meta["verified_fact_promotion"])
        for hyp in meta["hypotheses"][:5]:
            self.assertTrue(hyp["predictions"])
            self.assertTrue(hyp["falsifiers"])
            self.assertTrue(hyp["observations"])
            self.assertEqual(hyp["status"], "proposed")

    def test_hypotheses_are_persistent_but_not_verified_facts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            k = root / "knowledge"
            k.mkdir(parents=True)
            (k / "seed.jsonl").write_text(
                json.dumps({
                    "id": "system-x",
                    "title": "系X",
                    "domain": "test",
                    "text": (
                        "系Xは入力Aと入力Bの相互作用を受ける。"
                        "観測量Yには測定誤差がある。"
                        "条件によって支配要因が変化する。"
                    ),
                }, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (k / "scientific_models_ja.jsonl").write_text(
                json.dumps({
                    "id": "system_x_model",
                    "title": "系X",
                    "domain": "test",
                    "aliases": ["系X"],
                    "variables": ["観測量Y"],
                    "drivers": ["入力A", "入力B"],
                    "equations": [],
                    "mechanism": ["入力Aと入力Bが系Xへ影響する。"],
                    "scales": ["条件により支配要因が変化する。"],
                    "assumptions": [],
                    "observables": ["観測量Y"],
                    "limits": ["測定誤差が残る。"],
                }, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            engine = HypothesisEngine(root)
            first = engine.run("系Xについて別の仮説と反証案を考えて", [])
            self.assertIsNotNone(first)
            self.assertEqual(first["generated_hypotheses"], 5)
            self.assertFalse(first["verified_fact_promotion"])
            self.assertGreaterEqual(first["hypothesis_memory"]["added"], 1)

            second = engine.run("系Xについて別の仮説と反証案を考えて", [])
            self.assertIsNotNone(second)
            self.assertGreaterEqual(second["hypothesis_memory"]["updated"], 1)
            self.assertGreaterEqual(engine.ledger.stats()["items"], 1)

    def test_ordinary_equation_explanation_stays_on_scientific_model_route(self):
        core = FAPV8752Unified()
        out = core.chat(
            "大気の動き方を式も含めて解説して",
            "v8752-science-route-preserved",
        )
        self.assertIn("scientific-model", out["route"])
        self.assertNotIn("hypothesis-generate", out["route"])


if __name__ == "__main__":
    unittest.main()
