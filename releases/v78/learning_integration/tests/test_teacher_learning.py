from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V75 = RELEASES / "v75" / "managed_chat"
V71 = RELEASES / "v71" / "runtime"
V69 = RELEASES / "v69" / "interaction"

for path in (ROOT, V75, V71, V69):
    sys.path.insert(0, str(path))

from fap_teacher_learning import (
    LearnedManagedChat,
    LearningArtifactError,
    TeacherLearningResponder,
    TeacherLearningState,
    build_interaction_runtime,
)


class TeacherLearningTests(unittest.TestCase):
    def setUp(self):
        self.state = TeacherLearningState()
        self.responder = TeacherLearningResponder(self.state)

    def test_artifact_integrity_and_counts_match_kaggle_passed_export(self):
        status = self.state.status()
        self.assertEqual(status.circuits, 10)
        self.assertEqual(status.memory_items, 22)
        self.assertEqual(status.concept_nodes, 28)
        self.assertEqual(status.concept_edges, 27)
        self.assertEqual(status.source_selftest, "PASS")
        self.assertEqual(
            status.source_artifact_sha256,
            "e12f51a37681d3aabb4dd00d320fe1bf31362a7e939e454b4e7abc1f7db66909",
        )

    def test_teacher_memory_stays_shadow_weighted(self):
        self.assertTrue(self.state.memory)
        for item in self.state.memory:
            self.assertEqual(item["source"], "teacher_shadow")
            self.assertLessEqual(float(item["weight"]), 1.0)

    def test_repair_uncertainty_and_debugging_circuits_activate(self):
        cases = [
            ("違う、速度ではなくRAM制約を優先してください", "conversation_repair"),
            ("これは不確実なので仮説と確定事実を分けて", "uncertainty"),
            ("このエラーの最初の失敗点からデバッグして", "debugging"),
        ]
        for text, expected in cases:
            names = [x.name for x in self.responder.activate(text)]
            self.assertIn(expected, names, (text, names))

    def test_context_followup_uses_prior_context(self):
        active = self.responder.activate(
            "それの続きは？",
            "user: 前の設計について\nassistant: 設計A",
        )
        self.assertIn("context_followup", [x.name for x in active])

    def test_rich_direct_response_labels_shadow_as_unverified(self):
        text = self.responder.respond("これは仮説なので検証して", mode="rich")
        self.assertIn("適用回路:", text)
        if "Teacher shadow" in text:
            self.assertIn("未検証", text)

    def test_wrap_augments_context_but_keeps_base_responder_in_control(self):
        seen = {}

        def base(user_text, context, mode):
            seen["user_text"] = user_text
            seen["context"] = context
            seen["mode"] = mode
            return "BASE-OK"

        wrapped = self.responder.wrap(base)
        result = wrapped("エラーを最小再現から修正して", "prior", "rich")
        self.assertEqual(result, "BASE-OK")
        self.assertEqual(seen["user_text"], "エラーを最小再現から修正して")
        self.assertEqual(seen["mode"], "rich")
        self.assertIn("[FAP teacher-learning guidance]", seen["context"])
        self.assertIn("debugging", seen["context"])

    def test_managed_chat_integration_preserves_v75_commands_and_bounds(self):
        chat = LearnedManagedChat(
            max_exchanges=2,
            max_context_chars=600,
            max_input_chars=200,
        )
        self.assertIn("mode=rich", chat.submit(":status"))
        self.assertEqual(chat.submit(":brief"), "mode=brief")
        response = chat.submit("エラーを切り分けて修正して")
        self.assertIn("debugging", response)
        chat.submit("次に検証して")
        chat.submit("それの続き")
        self.assertLessEqual(len(chat.turns), 4)
        self.assertLessEqual(chat.status().context_chars, 600)

    def test_v71_interaction_runtime_uses_learned_chat_responder(self):
        runtime = build_interaction_runtime()
        result = runtime.chat("不確実な仮説を検証して")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.kind, "chat")
        self.assertIn("uncertainty", result.text)
        mode = runtime.chat(":brief")
        self.assertEqual(mode.text, "mode=brief")

    def test_tampered_learning_data_fails_closed(self):
        source = ROOT / "fap_teacher_learning" / "data"
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            for path in source.iterdir():
                shutil.copy2(path, target / path.name)
            circuits = json.loads(
                (target / "teacher_consolidated_circuits.json").read_text(encoding="utf-8")
            )
            circuits["debugging"]["detect"].append("tampered")
            (target / "teacher_consolidated_circuits.json").write_text(
                json.dumps(circuits, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LearningArtifactError, "digest mismatch"):
                TeacherLearningState(target)


if __name__ == "__main__":
    unittest.main()
