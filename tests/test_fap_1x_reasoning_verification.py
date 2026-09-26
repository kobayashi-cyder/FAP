from __future__ import annotations

from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

from fap_1x_algebra_solver import GenericLinearEquationSolver
from fap_1x_candidate_verifier import IndependentCandidateVerifier
from fap_1x_confidence_calibrator import ConfidenceCalibrator
from fap_1x_grounded_retrieval import GroundedRetrievalReasoner
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_1x_external_eval import IsolatedHoldoutEvaluator
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


class GenericLinearEquationSolverTests(unittest.TestCase):
    def test_solves_unseen_integer_equation_and_substitutes(self):
        solver = GenericLinearEquationSolver()
        out = solver.run("Solve for x: 7x + 5 = 40")
        self.assertIsNotNone(out)
        self.assertTrue(out["algebra_verified"])
        self.assertIn("x=5", out["reply"])

    def test_find_prefix_does_not_truncate_coefficient_expression(self):
        solver = GenericLinearEquationSolver()
        out = solver.run("Find x: 4 * x + 3 = 23")
        self.assertIsNotNone(out)
        self.assertEqual(out["algebra_result"]["value"], "5")

    def test_solves_fractional_result(self):
        solver = GenericLinearEquationSolver()
        out = solver.run("Solve for y: 6y - 1 = 8")
        self.assertIsNotNone(out)
        self.assertEqual(out["algebra_result"]["value"], "3/2")

    def test_mcq_answer_position_is_not_hardcoded(self):
        solver = GenericLinearEquationSolver()
        prompt = mcq("Solve for z: 4z + 3 = 23", ("4", "6", "5", "7"))
        out = solver.run(prompt)
        self.assertIsNotNone(out)
        self.assertIn("Answer: $C", out["reply"])

    def test_nonlinear_equation_declines(self):
        solver = GenericLinearEquationSolver()
        self.assertIsNone(solver.run("Solve for x: x^2 = 9"))


class IsolatedHoldoutEvaluatorTests(unittest.TestCase):
    def test_answer_key_outside_repo_and_scored_after_inference(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            prompts = folder / "prompts.jsonl"
            answers = folder / "answers.jsonl"
            prompts.write_text(
                json.dumps(
                    {
                        "id": "arith-1",
                        "domain": "math",
                        "prompt": mcq("What is 19 + 23?", ("40", "41", "42", "43")),
                    },
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )
            answers.write_text(
                json.dumps(
                    {"id": "arith-1", "answer": "C", "mode": "mcq"},
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )
            report = IsolatedHoldoutEvaluator(ROOT).run(prompts, answers)
            self.assertEqual(report["items"], 1)
            self.assertEqual(report["correct"], 1)
            self.assertEqual(report["accuracy"], 1.0)
            self.assertEqual(report["coverage"], 1.0)
            self.assertIn("brier", report)
            self.assertIn("ece_10", report)
            self.assertNotEqual(report["prompt_sha256"], report["answer_sha256"])

    def test_in_repo_answer_key_is_rejected(self):
        evaluator = IsolatedHoldoutEvaluator(ROOT)
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            evaluator._ensure_isolated_answer_file(ROOT / "tests" / "answers.jsonl")


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


class ConfidenceCalibratorTests(unittest.TestCase):
    def test_supported_and_provisional_are_capped_below_verified(self):
        calibrator = ConfidenceCalibrator()
        verified = calibrator.calibrate(
            verification="verified",
            generator_confidence=0.99,
            verifier_score=1.0,
            evidence_count=4,
            repeated_verification=True,
        )
        supported = calibrator.calibrate(
            verification="supported",
            generator_confidence=0.99,
            verifier_score=0.8,
            evidence_count=4,
        )
        provisional = calibrator.calibrate(
            verification="provisional",
            generator_confidence=0.99,
            verifier_score=0.0,
            evidence_count=4,
        )
        self.assertGreater(verified.confidence, supported.confidence)
        self.assertGreater(supported.confidence, provisional.confidence)
        self.assertLessEqual(supported.confidence, 0.78)
        self.assertLessEqual(provisional.confidence, 0.48)


class GroundedRetrievalReasonerTests(unittest.TestCase):
    def test_extracts_existing_knowledge_with_evidence(self):
        reasoner = GroundedRetrievalReasoner(ROOT)
        out = reasoner.run("コリオリ効果とは？", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["ok"])
        self.assertTrue(out["grounded"])
        self.assertIn("coriolis", out["evidence_ids"])
        self.assertIn("北半球", out["reply"])

    def test_core_uses_retrieval_as_supported_not_verified(self):
        core = FAP1xGeneralReasoningCore(ROOT)
        out = core.solve("コリオリ効果とは？")
        self.assertIsNotNone(out)
        self.assertTrue(out["ok"])
        self.assertEqual(out["reasoning_source"], "grounded_retrieval")
        self.assertEqual(out["verification_state"], "supported")
        report = out["selected_payload"]["independent_verification"]
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verifier"], "fresh_grounded_retrieval_replay")


class ContextIsolationTests(unittest.TestCase):
    def test_user_subject_beats_assistant_generated_subject(self):
        reasoner = GenericRuleReasoner(ROOT)
        history = [
            {"role": "user", "text": "四角形について考える"},
            {
                "role": "assistant",
                "text": "三角形の内角の和は180度です。三角形について詳しく説明します。",
            },
        ]
        out = reasoner.run("内角の和は？", history)
        self.assertIsNotNone(out)
        self.assertEqual(out["context_source"], "conversation-context")
        self.assertIn("360", out["reply"])
        self.assertNotIn("180° です。", out["reply"])


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
