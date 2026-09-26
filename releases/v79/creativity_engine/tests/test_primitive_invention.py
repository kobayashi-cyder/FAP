import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity.primitive_invention import (
    Instruction,
    MiniIRSandbox,
    PrimitiveInventor,
    PrimitivePromotionLoop,
    PrimitiveTestCase,
    SkillRegistry,
)


class PrimitiveInventionLoopTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = MiniIRSandbox(timeout_ms=50)
        self.inventor = PrimitiveInventor(self.sandbox)

    def test_invent_string_primitive_and_promote_after_three_shadow_successes(self):
        tests = [
            PrimitiveTestCase("  HELLO  ", "hello"),
            PrimitiveTestCase("World", "world"),
            PrimitiveTestCase("  FAP", "fap"),
            PrimitiveTestCase("MiXeD  ", "mixed"),
            PrimitiveTestCase("   ", "", boundary=True, label="whitespace-empty"),
        ]
        candidate = self.inventor.invent_from_examples(
            name="normalize_text",
            input_kind="string",
            examples=tests,
            max_depth=2,
        )
        self.assertEqual([op.op for op in candidate.program], ["strip", "lower"])

        loop = PrimitivePromotionLoop(sandbox=self.sandbox)
        decision = loop.evaluate(
            candidate,
            shadow_cases=[
                PrimitiveTestCase("  ALPHA", "alpha"),
                PrimitiveTestCase("Beta  ", "beta"),
                PrimitiveTestCase(" GAMMA ", "gamma"),
            ],
        )
        self.assertTrue(decision.promoted)
        self.assertEqual(decision.stage, "active")
        self.assertEqual(decision.shadow_successes, 3)
        result = loop.execute_active(candidate.primitive_id, "  DELTA  ")
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "delta")

    def test_stays_shadow_without_three_real_successes(self):
        tests = [
            PrimitiveTestCase([1, 1, 2], [1, 2]),
            PrimitiveTestCase(["a", "a"], ["a"]),
            PrimitiveTestCase([1, 2, 1], [1, 2]),
            PrimitiveTestCase([], [], boundary=True),
            PrimitiveTestCase([True, True, False], [True, False]),
        ]
        candidate = self.inventor.invent_from_examples(
            name="dedupe",
            input_kind="list",
            examples=tests,
        )
        loop = PrimitivePromotionLoop(sandbox=self.sandbox)
        decision = loop.evaluate(candidate, shadow_cases=[PrimitiveTestCase([3, 3], [3])])
        self.assertEqual(decision.stage, "shadow")
        self.assertFalse(decision.promoted)
        self.assertEqual(decision.shadow_successes, 1)

    def test_rejects_less_than_five_tests(self):
        candidate = self.inventor.compose(
            name="abs_value",
            input_kind="number",
            program=[Instruction("abs")],
            tests=[
                PrimitiveTestCase(-1, 1),
                PrimitiveTestCase(0, 0, boundary=True),
                PrimitiveTestCase(2, 2),
                PrimitiveTestCase(-3, 3),
            ],
        )
        decision = PrimitivePromotionLoop(sandbox=self.sandbox).evaluate(candidate)
        self.assertEqual(decision.stage, "rejected")
        self.assertTrue(any("at least 5" in reason for reason in decision.reasons))

    def test_rejects_banned_or_unknown_instruction(self):
        candidate = self.inventor.compose(
            name="unsafe",
            input_kind="string",
            program=[Instruction("exec", ("x",))],
            tests=[PrimitiveTestCase("a", "a", boundary=True)] * 5,
        )
        decision = PrimitivePromotionLoop(sandbox=self.sandbox).evaluate(candidate)
        self.assertEqual(decision.stage, "rejected")
        self.assertTrue(any("banned" in reason for reason in decision.reasons))

    def test_registry_persists_active_skill(self):
        tests = [
            PrimitiveTestCase(-2, 2),
            PrimitiveTestCase(-1, 1),
            PrimitiveTestCase(0, 0, boundary=True),
            PrimitiveTestCase(1, 1),
            PrimitiveTestCase(2, 2),
        ]
        candidate = self.inventor.invent_from_examples(
            name="absolute",
            input_kind="number",
            examples=tests,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            registry = SkillRegistry(path)
            loop = PrimitivePromotionLoop(sandbox=self.sandbox, registry=registry)
            decision = loop.evaluate(
                candidate,
                shadow_cases=[
                    PrimitiveTestCase(-10, 10),
                    PrimitiveTestCase(-7, 7),
                    PrimitiveTestCase(9, 9),
                ],
            )
            self.assertEqual(decision.stage, "active")
            loaded = SkillRegistry(path)
            self.assertEqual(loaded.get(candidate.primitive_id)["stage"], "active")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "fap.primitive-registry.v1")


if __name__ == "__main__":
    unittest.main()
