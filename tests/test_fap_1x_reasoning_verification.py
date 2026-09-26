from __future__ import annotations

from pathlib import Path
import unittest

from fap_1x_candidate_verifier import IndependentCandidateVerifier
from fap_1x_problem_decomposer import ProblemDecomposer
from fap_1x_search_controller import AdaptiveSearchController
from fap_1x_reasoning_core import FAP1xGeneralReasoningCore


ROOT = Path(__file__).resolve().parents[1]


def mcq(question: str, choices: tuple[str, str, str, str]) -> str:
    return (
        "Answer the following multiple choice question.\n"
        "The last line of your response should be: Answer: $LETTER\n\n"
        + question
        + "\n\n"
        + "\n".join(f"{letter}) {value}" for letter, value in zip("ABCD", choices))
    )


class ProblemDecomposerTests(unittest.TestCase):
    def test_dependency_graph_contains_verify_and_counterexample(self):
        model = ProblemDecomposer().decompose(
            "電流 3 A、抵抗 7 ohms から電圧を計算し、推測せず検証してください"
        )
        ids = [row.subproblem_id for row in model.subproblems]
        self.assertIn("derive", ids)
        self.assertIn("verify", ids)
        self.assertIn("counterexample", ids)
        self.assertIn("synthesize", ids)
        verify = next(row for row in model.subproblems if row.subproblem_id == "verify")
        counter = next(row for row in model.subproblems if row.subproblem_id == "counterexample")
        self.assertEqual(verify.depends_on, ("derive",))
        self.assertEqual(counter.depends_on, ("verify",))
        self.assertTrue(model.givens)

    def test_coding_plan_is_not_treated_as_numeric_derivation(self):
        model = ProblemDecomposer().decompose(
            "repositoryの parser.py を修正して tests を通す。ただし既存APIは壊さない"
        )
        self.assertEqual(model.task_kind, "coding")
        kinds = [row.kind for row in model.subproblems]
        self.assertIn("repository_analysis", kinds)
        self.assertIn("candidate_generation", kinds)
        self.assertIn("verification", kinds)


class AdaptiveSearchControllerTests(unittest.TestCase):
    def test_low_risk_task_stays_sparse(self):
        model = ProblemDecomposer().decompose("四角形の内角の和は？")
        policy = AdaptiveSearchController().policy(
            model,
            disagreement=False,
            candidate_verifications=("verified",),
        )
        self.assertEqual(policy.max_rounds, 1)
        self.assertLessEqual(policy.branch_budget, 3)
        self.assertFalse(policy.repeat_independent_verification)

    def test_high_risk_or_disagreement_densifies_and_requires_verification(self):
        model = ProblemDecomposer().decompose(
            "この複雑な導出を証明してください。条件A以上、条件B以内、推測せず必ず検証してください。"
            + "追加の前提と長い説明を含めます。" * 30
        )
        policy = AdaptiveSearchController().policy(
            model,
            disagreement=True,
            candidate_verifications=("supported", "verified"),
        )
        self.assertGreaterEqual(policy.max_rounds, 3)
        self.assertGreaterEqual(policy.branch_budget, 10)
        self.assertTrue(policy.require_verified)
        self.assertTrue(policy.repeat_independent_verification)
        self.assertFalse(policy.allow_supported)


class IndependentCandidateVerifierTests(unittest.TestCase):
    def setUp(self):
        self.verifier = IndependentCandidateVerifier(ROOT)
        self.core = FAP1xGeneralReasoningCore(ROOT)

    def test_arithmetic_is_recomputed_outside_generator(self):
        prompt = mcq("What is 37 + 28?", ("63", "64", "65", "66"))
        result = self.core.solve(prompt)
        self.assertEqual(result["reasoning_source"], "verified_arithmetic")
        report = result["selected_payload"]["independent_verification"]
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verifier"], "arithmetic_recompute")

    def test_physics_is_recomputed_from_formula_details(self):
        prompt = mcq(
            "In an Ohm's law circuit, current is 4 A and resistance is 6 ohms. What is the voltage?",
            ("18 V", "20 V", "24 V", "28 V"),
        )
        result = self.core.solve(prompt)
        self.assertEqual(result["reasoning_source"], "deterministic_physics")
        report = result["selected_payload"]["independent_verification"]
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verifier"], "physics_formula_recompute")

    def test_tampered_arithmetic_candidate_is_rejected(self):
        prompt = mcq("What is 37 + 28?", ("63", "64", "65", "66"))
        payload = {
            "ok": True,
            "reply": "Answer: $D",
            "decision_source": "verified_arithmetic",
        }
        report = self.verifier.verify("verified_arithmetic", prompt, [], payload)
        self.assertEqual(report.status, "failed")

    def test_problem_decomposition_is_exposed_in_reasoning_result(self):
        result = self.core.solve("四角形の内角の和は？")
        model = result["problem_decomposition"]
        self.assertIn("subproblems", model)
        self.assertTrue(any(row["subproblem_id"] == "verify" for row in model["subproblems"]))
        self.assertTrue(any(row["subproblem_id"] == "counterexample" for row in model["subproblems"]))


if __name__ == "__main__":
    unittest.main()
