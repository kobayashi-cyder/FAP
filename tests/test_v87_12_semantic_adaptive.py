from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fap_v87_10_program_synth_gateway as base
from fap_semantic_memory import AdaptiveRoutingLedger, SemanticMemoryStore
from fap_v87_12_semantic_adaptive_gateway import FAPV8712


class V8712SemanticAdaptiveTests(unittest.TestCase):
    def test_semantic_memory_merges_repeated_preference(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SemanticMemoryStore(Path(td))
            for _ in range(6):
                mem.absorb_user("s", "標準の出力言語は日本語にする。")
            state = mem.load("s")
            rows = [x for x in state["entries"] if x.get("slot") == "preference:output_language"]
            self.assertEqual(len(rows), 1)
            self.assertGreaterEqual(rows[0]["mentions"], 6)

    def test_preference_new_value_supersedes_old_value(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SemanticMemoryStore(Path(td))
            mem.absorb_user("s", "標準の出力言語は日本語にする。")
            mem.absorb_user("s", "標準の出力言語は英語にする。")
            out = mem.render("s", "標準の出力言語は？")
            self.assertIn("英語", out)
            self.assertNotIn("- 設定: 標準の出力言語は日本語にする", out)

    def test_noise_is_not_promoted_to_long_term_memory(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SemanticMemoryStore(Path(td))
            for i in range(80):
                mem.absorb_user("s", f"雑談メモ{i}")
            self.assertEqual(mem.stats("s")["entries"], 0)

    def test_compaction_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SemanticMemoryStore(Path(td))
            for i in range(180):
                mem.absorb_user("s", f"これを覚えて: テスト情報{i}は値{i}です")
            self.assertLessEqual(mem.stats("s")["entries"], mem.MAX_ENTRIES)

    def test_adaptive_router_learns_implicit_code_request(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = AdaptiveRoutingLedger(Path(td) / "route.json")
            ledger.record("Pythonで文字数を数えるコードを作って", "builder", "OK")
            ledger.record("Pythonで単語数を数えるコードを作って", "builder", "OK")
            intent = base.Intent("chat", 0.55, [("chat", 0.40), ("builder", 0.02)])
            out = ledger.suggest("Pythonで文字数を数えるコードお願い", intent)
            self.assertTrue(out["applied"])
            self.assertEqual(out["selected"], "builder")

    def test_explicit_intent_cannot_be_overridden_by_learning(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = AdaptiveRoutingLedger(Path(td) / "route.json")
            for _ in range(5):
                ledger.record("コードの相談", "chat", "OK")
            intent = base.Intent("builder", 0.95, [("builder", 1.1), ("chat", 0.18)])
            out = ledger.suggest("Pythonコードを作って", intent)
            self.assertFalse(out["applied"])
            self.assertEqual(out["selected"], "builder")
            self.assertIn("locked", out["reason"])

    def test_core_recalls_preference_after_raw_history_eviction(self):
        core = FAPV8712()
        sid = "v8712-long-semantic"
        core.chat("標準の出力言語は日本語にする。", sid)
        for i in range(base.MAX_HISTORY + 12):
            core.chat(f"雑談メモ{i}", sid)
        out = core.chat("標準の出力言語は？", sid)
        self.assertEqual(out["ability"], "memory")
        self.assertIn("日本語", out["reply"])
        self.assertLessEqual(len(base.MEMORY.load(sid)), base.MAX_HISTORY)

    def test_codegen_is_preserved(self):
        core = FAPV8712()
        out = core.chat("Pythonで文章から数字だけ抽出して合計を出すコードを作って", "v8712-code")
        self.assertEqual(out["ability"], "builder")
        self.assertTrue(out["artifacts"])
        self.assertEqual(out["verdict"], "OK")


    def test_adaptive_routing_changes_real_chat_for_implicit_code_request(self):
        with tempfile.TemporaryDirectory() as td:
            core = FAPV8712()
            core.adaptive = AdaptiveRoutingLedger(Path(td) / "route.json")
            sid = "v8712-adaptive-chat"
            a = core.chat("Pythonで文章の文字数を数えるコードを作って", sid)
            b = core.chat("Pythonで文章の単語数を数えるコードを作って", sid)
            self.assertEqual(a["verdict"], "OK")
            self.assertEqual(b["verdict"], "OK")
            out = core.chat("Pythonで文章の文字数を数えるコードお願い", sid)
            self.assertEqual(out["ability"], "builder")
            self.assertTrue(out["adaptive_routing"]["applied"])
            self.assertTrue(out["artifacts"])
            self.assertEqual(out["verdict"], "OK")

    def test_status_exposes_semantic_and_adaptive_layers(self):
        st = FAPV8712().status()
        self.assertEqual(st["version"], "87.12-semantic-adaptive")
        self.assertEqual(st["reasoning_controller"]["raw_history_turns"], 48)
        self.assertTrue(st["reasoning_controller"]["semantic_memory"])
        self.assertTrue(st["reasoning_controller"]["adaptive_routing"])


if __name__ == "__main__":
    unittest.main()
