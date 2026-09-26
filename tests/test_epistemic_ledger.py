from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fap_1x_standard_runtime import FAP1xStandardRuntime
from fap_epistemic_ledger import EpistemicConflictLedger


ROOT = Path(__file__).resolve().parents[1]


def conflict_payload() -> dict:
    return {
        "reply": "候補間に検証済みの不一致があります。",
        "confidence": 0.68,
        "needs_teacher": True,
        "reasoning_episode": {
            "contract": "fap.reasoning.episode.v1",
            "verdict": "BLOCKED",
        },
        "response_series_execution": {
            "selected": "factual",
            "verified_disagreements": [["factual", "rule"]],
            "candidates": [
                {"id": "factual", "verified": True},
                {"id": "rule", "verified": True},
            ],
        },
    }


def resolved_payload() -> dict:
    return {
        "reply": "再検証済みです。",
        "confidence": 0.98,
        "reasoning_episode": {
            "contract": "fap.reasoning.episode.v1",
            "verdict": "OK",
        },
        "response_series_execution": {
            "selected": "factual",
            "verified_disagreements": [],
            "candidates": [
                {"id": "factual", "verified": True},
            ],
        },
    }


class EpistemicConflictLedgerTests(unittest.TestCase):
    def test_conflict_is_separate_relevant_and_resolvable(self):
        with TemporaryDirectory() as tmp:
            ledger = EpistemicConflictLedger(Path(tmp))
            topic = "真空中の光速について厳密に確認して"
            first = ledger.observe("s", topic, conflict_payload())
            self.assertEqual(first["active_count"], 1)
            self.assertTrue(first["recorded"])

            related = ledger.relevant("s", "真空中の光速をもう一度確認して")
            self.assertEqual(len(related), 1)
            self.assertEqual(
                ledger.relevant("s", "自然選択について説明して"),
                [],
            )

            final = ledger.observe("s", topic, resolved_payload())
            self.assertEqual(final["active_count"], 0)
            self.assertTrue(final["resolved"])
            self.assertFalse(ledger.snapshot("s")[0]["active"])

    def test_persisted_file_contains_no_raw_conversation_or_candidate_prose(self):
        with TemporaryDirectory() as tmp:
            ledger = EpistemicConflictLedger(Path(tmp))
            raw = "秘密の生会話XYZ-731について厳密に確認して"
            ledger.observe("s", raw, conflict_payload())
            stored = (Path(tmp) / "epistemic_conflicts.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("秘密の生会話", stored)
            self.assertNotIn("候補間に検証済みの不一致", stored)
            self.assertIn(EpistemicConflictLedger.CONTRACT, stored)

            loaded = EpistemicConflictLedger(Path(tmp))
            self.assertEqual(loaded.active_count(), 1)
            self.assertTrue(loaded.relevant("s", raw))

    def test_runtime_prior_conflict_forces_reverification_then_resolves(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        topic = "真空中の光速は？"
        runtime.epistemic_ledger.observe(
            "recheck",
            topic,
            conflict_payload(),
        )
        result = runtime.run_turn(topic, session_id="recheck")
        self.assertEqual(result.state, "handled")
        self.assertIn("299,792,458", result.payload.get("reply", ""))

        ledger = result.payload.get("epistemic_ledger") or {}
        governor = result.payload.get("reasoning_governor") or {}
        episode = result.payload.get("reasoning_episode") or {}
        self.assertEqual(ledger.get("related_before"), 1)
        self.assertTrue(ledger.get("resolved"))
        self.assertEqual(ledger.get("active_count"), 0)
        self.assertGreaterEqual(governor.get("passes", 0), 2)
        self.assertEqual(episode.get("verdict"), "OK")
        self.assertTrue(result.payload.get("prior_epistemic_conflict"))

    def test_clear_session_clears_conflicts_too(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        runtime.epistemic_ledger.observe(
            "clear-me",
            "計算結果について確認して",
            conflict_payload(),
        )
        self.assertTrue(runtime.epistemic_snapshot("clear-me"))
        runtime.clear_session("clear-me")
        self.assertEqual(runtime.epistemic_snapshot("clear-me"), ())


if __name__ == "__main__":
    unittest.main()
