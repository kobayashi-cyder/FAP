from __future__ import annotations

from pathlib import Path
import unittest

from fap_1x_reasoning_core import FAP1xGeneralReasoningCore
from fap_1x_standard_runtime import FAP1xStandardRuntime


ROOT = Path(__file__).resolve().parents[1]


def mcq(question: str, choices: tuple[str, str, str, str]) -> str:
    return (
        "Answer the following multiple choice question.\n"
        "The last line of your response should be: Answer: $LETTER\n\n"
        + question
        + "\n\n"
        + "\n".join(
            f"{letter}) {value}"
            for letter, value in zip("ABCD", choices)
        )
    )


class FAP1xGeneralReasoningCoreTests(unittest.TestCase):
    def setUp(self):
        self.core = FAP1xGeneralReasoningCore(ROOT)

    def test_verified_arithmetic_beats_unresolved_fallback(self):
        prompt = mcq("What is 17 + 29?", ("44", "45", "46", "47"))
        result = self.core.solve(prompt)
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reasoning_source"], "verified_arithmetic")
        self.assertEqual(result["verification_state"], "verified")
        self.assertIn("Answer: $C", result["reply"])

    def test_deterministic_physics_is_verified_candidate(self):
        prompt = mcq(
            "In an Ohm's law circuit, current is 3 A and resistance is 7 ohms. "
            "What is the voltage?",
            ("14 V", "18 V", "21 V", "24 V"),
        )
        result = self.core.solve(prompt)
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reasoning_source"], "deterministic_physics")
        self.assertEqual(result["verification_state"], "verified")
        self.assertIn("Answer: $C", result["reply"])

    def test_unresolved_mcq_is_not_answered_by_hash_tiebreak(self):
        prompt = mcq(
            "Which option is correct about ZXQV-938271?",
            ("alpha", "beta", "gamma", "delta"),
        )
        result = self.core.solve(prompt)
        self.assertIsNone(result)

    def test_rule_reasoning_is_selected_as_verified(self):
        result = self.core.solve("四角形の内角の和は？")
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reasoning_source"], "rule_verified")
        self.assertEqual(result["verification_state"], "verified")
        self.assertIn("360", result["reply"])

    def test_symbolic_derivation_uses_counterchecked_lane(self):
        result = self.core.solve("三平方の定理を導出して")
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reasoning_source"], "derivation_verified")
        self.assertEqual(result["verification_state"], "verified")
        self.assertIn("a^2 + b^2 = c^2", result["reply"])

    def test_standard_runtime_routes_through_reasoning_core(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("四角形の内角の和は？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "general_reasoning_core")
        self.assertEqual(result.payload["verification_state"], "verified")

    def test_standard_runtime_fails_closed_on_unknown_mcq(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        prompt = mcq(
            "Which option is correct about ZXQV-938271?",
            ("alpha", "beta", "gamma", "delta"),
        )
        result = runtime.run_turn(prompt)
        self.assertEqual(result.state, "unhandled")


if __name__ == "__main__":
    unittest.main()
