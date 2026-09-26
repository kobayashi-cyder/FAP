from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V79 = RELEASES / "v79" / "creativity_engine"
V78 = RELEASES / "v78" / "learning_integration"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V79))
sys.path.insert(0, str(V78))

from fap_local_adaptation import (
    FixedReservoir,
    LocalAdaptiveCore,
    LocalAdaptiveResponder,
    build_v81_responder,
    encode_text,
)


class LocalAdaptationTests(unittest.TestCase):
    def test_encoder_is_deterministic_and_bounded(self):
        a = encode_text("FAP 次入力 予測", 24)
        b = encode_text("FAP 次入力 予測", 24)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)
        self.assertLessEqual(sum(x * x for x in a), 1.000001)

    def test_fixed_reservoir_digest_does_not_change_with_local_overlay(self):
        core = LocalAdaptiveCore()
        before = core.reservoir.fixed_digest()
        for i in range(8):
            core.learn_transition(
                source_text="成功する局所回路",
                target_text="次の入力",
                evidence_id=f"hebb-{i}",
                verified=True,
                success=True,
            )
        self.assertEqual(before, core.reservoir.fixed_digest())
        self.assertGreater(len(core.reservoir.plastic_overlay), 0)

    def test_predictive_error_falls_on_repeated_verified_transition(self):
        core = LocalAdaptiveCore()
        source = "画面が切り替わる"
        target = "元のアプリを呼び戻す"
        before = core.transition_error(source, target)
        for i in range(80):
            core.learn_transition(
                source_text=source,
                target_text=target,
                evidence_id=f"predict-{i}",
                verified=True,
                success=True,
            )
        after = core.transition_error(source, target)
        self.assertLess(after, before * 0.65)

    def test_unverified_observation_cannot_change_learning_state(self):
        core = LocalAdaptiveCore()
        weights_before = copy.deepcopy(core.readout.weights)
        overlay_before = dict(core.reservoir.plastic_overlay)
        result = core.learn_transition(
            source_text="未検証",
            target_text="学習禁止",
            evidence_id="unverified",
            verified=False,
            success=True,
        )
        self.assertFalse(result.learned)
        self.assertEqual(weights_before, core.readout.weights)
        self.assertEqual(overlay_before, core.reservoir.plastic_overlay)
        self.assertEqual(core.seen_learning_evidence, set())

    def test_verified_success_changes_only_bounded_local_overlay(self):
        core = LocalAdaptiveCore()
        for i in range(120):
            core.learn_transition(
                source_text=f"成功パターン {i % 5}",
                target_text=f"次状態 {i % 7}",
                evidence_id=f"bounded-{i}",
                verified=True,
                success=True,
            )
        self.assertLessEqual(len(core.reservoir.plastic_overlay), core.hebb.max_edges)
        self.assertTrue(
            all(abs(w) <= core.hebb.max_weight + 1e-12 for w in core.reservoir.plastic_overlay.values())
        )

    def test_verified_failure_becomes_counterexample_not_hebb_reward(self):
        core = LocalAdaptiveCore()
        result = core.learn_transition(
            source_text="ブラウザへ逸脱して戻らない",
            target_text="失敗",
            evidence_id="failure-1",
            verified=True,
            success=False,
            action_tag="navigation",
            failure_severity=0.95,
        )
        self.assertTrue(result.learned)
        self.assertEqual(result.hebbian_edges_changed, 0)
        self.assertTrue(result.counterexample_added)
        penalty = core.counterexamples.penalty(
            "ブラウザへ逸脱して戻らない",
            "navigation",
        )
        self.assertGreaterEqual(penalty, 0.90)

    def test_counterexample_penalty_is_action_sensitive(self):
        core = LocalAdaptiveCore()
        core.learn_transition(
            source_text="同じボタンを無限連打",
            target_text="停止",
            evidence_id="failure-action",
            verified=True,
            success=False,
            action_tag="rapid_tap",
            failure_severity=1.0,
        )
        same = core.counterexamples.penalty("同じボタンを無限連打", "rapid_tap")
        other = core.counterexamples.penalty("同じボタンを無限連打", "navigation")
        self.assertGreater(same, other)

    def test_duplicate_verified_evidence_is_rejected_before_mutation(self):
        core = LocalAdaptiveCore()
        core.learn_transition(
            source_text="入力A",
            target_text="入力B",
            evidence_id="same-evidence",
            verified=True,
            success=True,
        )
        weights_before = copy.deepcopy(core.readout.weights)
        overlay_before = dict(core.reservoir.plastic_overlay)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            core.learn_transition(
                source_text="入力A",
                target_text="入力B",
                evidence_id="same-evidence",
                verified=True,
                success=True,
            )
        self.assertEqual(weights_before, core.readout.weights)
        self.assertEqual(overlay_before, core.reservoir.plastic_overlay)

    def test_passive_runtime_step_does_not_train(self):
        core = LocalAdaptiveCore()
        weights_before = copy.deepcopy(core.readout.weights)
        fixed_before = core.reservoir.fixed_digest()
        core.passive_step("一回目")
        stats = core.passive_step("二回目")
        self.assertIsNotNone(stats["prediction_error"])
        self.assertEqual(weights_before, core.readout.weights)
        self.assertEqual(fixed_before, core.reservoir.fixed_digest())
        self.assertEqual(core.seen_learning_evidence, set())

    def test_guidance_warns_on_similar_verified_failure(self):
        core = LocalAdaptiveCore()
        core.learn_transition(
            source_text="危険な再試行",
            target_text="失敗",
            evidence_id="avoid-1",
            verified=True,
            success=False,
            failure_severity=1.0,
        )
        guidance = core.guidance("危険な再試行")
        self.assertIn("[FAP local-adaptation guidance]", guidance)
        self.assertIn("avoidance_hint=", guidance)
        self.assertIn("verified_local_only", guidance)

    def test_state_round_trip_preserves_learned_components(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "v81_state.json"
            core = LocalAdaptiveCore()
            core.learn_transition(
                source_text="成功入力",
                target_text="成功次状態",
                evidence_id="persist-success",
                verified=True,
                success=True,
            )
            core.learn_transition(
                source_text="失敗入力",
                target_text="失敗次状態",
                evidence_id="persist-failure",
                verified=True,
                success=False,
                failure_severity=0.8,
            )
            expected_error = core.transition_error("成功入力", "成功次状態")
            core.save(path)

            restored = LocalAdaptiveCore()
            restored.load(path)
            self.assertEqual(core.reservoir.plastic_overlay, restored.reservoir.plastic_overlay)
            self.assertEqual(core.seen_learning_evidence, restored.seen_learning_evidence)
            self.assertEqual(len(core.counterexamples.records), len(restored.counterexamples.records))
            self.assertAlmostEqual(
                expected_error,
                restored.transition_error("成功入力", "成功次状態"),
                places=12,
            )

    def test_state_digest_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "v81_state.json"
            core = LocalAdaptiveCore()
            core.save(path)
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["payload"]["plastic_overlay"]["0:1"] = 0.1
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                LocalAdaptiveCore().load(path)

    def test_wrapper_keeps_base_responder_in_control(self):
        seen = {}

        def base(user_text, context, mode):
            seen["context"] = context
            return "BASE"

        wrapped = LocalAdaptiveResponder(base, core=LocalAdaptiveCore())
        self.assertEqual(wrapped("次を予測して", "prior", "rich"), "BASE")
        self.assertIn("[FAP local-adaptation guidance]", seen["context"])

    def test_v81_composes_with_v79_and_v78(self):
        seen = {}

        def base(user_text, context, mode):
            seen["context"] = context
            return "STACK"

        responder = build_v81_responder(base, core=LocalAdaptiveCore())
        result = responder("低RAMで新しい仕組みを考える", "prior", "rich")
        self.assertEqual(result, "STACK")
        self.assertIn("[FAP local-adaptation guidance]", seen["context"])
        self.assertIn("[FAP creativity guidance]", seen["context"])
        self.assertIn("[FAP teacher-learning guidance]", seen["context"])


if __name__ == "__main__":
    unittest.main()
