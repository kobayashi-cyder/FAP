from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
V86_ROOT = ROOT.parents[1] / "v86" / "generic_skill_factory"
V84_ROOT = ROOT.parents[1] / "v84" / "self_curriculum"
V82_ROOT = ROOT.parents[1] / "v82" / "adaptive_circuits"
sys.path.insert(0, str(V86_ROOT))
sys.path.insert(0, str(V84_ROOT))
sys.path.insert(0, str(V82_ROOT))
sys.path.insert(0, str(ROOT))

from fap_generic_skill import (
    BindingRegistry,
    GenericSkillFactory,
    SkillBinding,
    SkillBuildRequest,
    SkillTestCase,
)
from fap_self_curriculum import AbilityMap
from fap_autonomous_improvement import (
    AutonomousImprovementCore,
    CycleLedger,
    EvalCase,
    FAPEval,
    SkillEvolution,
    VerifiedSkillDeployment,
)


def bindings_for_cleanup() -> BindingRegistry:
    bindings = BindingRegistry()
    bindings.register(
        SkillBinding(
            "text.trim",
            lambda value: value.strip(),
            ("trim", "strip", "text"),
        )
    )
    bindings.register(
        SkillBinding(
            "text.lower",
            lambda value: value.lower(),
            ("lower", "normalize", "text"),
        )
    )
    bindings.register(
        SkillBinding(
            "text.reverse",
            lambda value: value[::-1],
            ("reverse", "text"),
        )
    )
    return bindings


def cleanup_request(name="cleanup repair") -> SkillBuildRequest:
    return SkillBuildRequest(
        "cleanup",
        name,
        ("trim", "lower"),
        0.65,
        (
            SkillTestCase(" A ", "a"),
            SkillTestCase("  Hello  ", "hello"),
            SkillTestCase("   ", "", boundary=True),
        ),
        (
            SkillTestCase(" B ", "b"),
            SkillTestCase("\tMixed CASE\n", "mixed case"),
            SkillTestCase(" Z ", "z"),
        ),
    )


class V90AutonomousImprovementTests(unittest.TestCase):
    def test_fap_eval_clusters_failures_and_contains_solver_errors(self):
        evaluator = FAPEval(
            (
                EvalCase("a", "cleanup", " A ", "a", 0.4),
                EvalCase("b", "identity", "x", "x", 0.2),
            )
        )

        def solver(case):
            if case.case_id == "a":
                raise RuntimeError("not ready")
            return case.payload

        result = evaluator.run(solver)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.passed, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(
            set(evaluator.failure_clusters(result)),
            {"cleanup"},
        )
        self.assertIn("RuntimeError", result.failures[0].error)

    def test_cycle_repairs_failure_and_deploys_only_after_global_eval(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup", "identity"])
        evaluator = FAPEval(
            (
                EvalCase("c1", "cleanup", " A ", "a", 0.5),
                EvalCase("c2", "cleanup", " B ", "b", 0.6),
                EvalCase("i1", "identity", "x", "x", 0.2),
            )
        )
        deployment = VerifiedSkillDeployment(factory)
        core = AutonomousImprovementCore(
            ability_map=amap,
            factory=factory,
            evaluator=evaluator,
            deployment=deployment,
        )

        result = core.cycle(
            cycle_id="repair-1",
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda ability, failures, attempt: (
                cleanup_request()
                if ability == "cleanup"
                else None
            ),
        )
        self.assertTrue(result.globally_accepted)
        self.assertEqual(result.reason, "global_eval_accepted")
        self.assertLess(result.before_accuracy, result.after_accuracy)
        self.assertEqual(result.after_accuracy, 1.0)
        self.assertEqual(len(result.locally_promoted_skills), 1)
        self.assertEqual(
            result.deployed_skills,
            result.locally_promoted_skills,
        )
        self.assertEqual(
            deployment.enabled,
            set(result.deployed_skills),
        )
        self.assertGreater(
            result.scorecard["cleanup"]["successes"],
            0,
        )

    def test_local_promotion_is_rolled_back_when_other_ability_regresses(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup", "text"])
        evaluator = FAPEval(
            (
                EvalCase("c1", "cleanup", "ABC", "abc", 0.5),
                EvalCase("t1", "text", "XYZ", "XYZ", 0.5),
            )
        )
        deployment = VerifiedSkillDeployment(factory)
        core = AutonomousImprovementCore(
            ability_map=amap,
            factory=factory,
            evaluator=evaluator,
            deployment=deployment,
        )
        request = SkillBuildRequest(
            "cleanup",
            "lower text repair",
            ("text",),
            0.6,
            (
                SkillTestCase("A", "a"),
                SkillTestCase("B", "b"),
                SkillTestCase("", "", boundary=True),
            ),
            (
                SkillTestCase("C", "c"),
                SkillTestCase("D", "d"),
                SkillTestCase("E", "e"),
            ),
        )

        result = core.cycle(
            cycle_id="regression-1",
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda ability, failures, attempt: request,
            max_repairs=1,
        )
        self.assertFalse(result.globally_accepted)
        self.assertEqual(result.reason, "global_eval_rejected")
        self.assertEqual(len(result.locally_promoted_skills), 1)
        self.assertEqual(result.deployed_skills, ())
        self.assertEqual(
            result.rolled_back_skills,
            result.locally_promoted_skills,
        )
        self.assertEqual(result.after_accuracy, result.before_accuracy)
        self.assertFalse(deployment.enabled)
        self.assertFalse(deployment.staged)

    def test_no_failures_performs_no_skill_invention(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["identity"])
        evaluator = FAPEval((EvalCase("i1", "identity", "x", "x"),))
        core = AutonomousImprovementCore(
            ability_map=amap,
            factory=factory,
            evaluator=evaluator,
        )
        calls = []
        result = core.cycle(
            cycle_id="clean-1",
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda *args: calls.append(args),
        )
        self.assertEqual(result.reason, "no_failures")
        self.assertEqual(result.attempted_repairs, 0)
        self.assertFalse(calls)
        self.assertEqual(result.after_accuracy, 1.0)

    def test_cycle_ledger_replay_protects_across_restart(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cycles.json"
            first = CycleLedger(path)
            first.reserve("cycle-1")
            second = CycleLedger(path)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                second.reserve("cycle-1")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["schema"],
                "fap.autonomous-improvement-ledger.v1",
            )

    def test_skill_evolution_mutates_only_verified_binding_references(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        spec, decision = factory.invent_and_promote(
            name="cleanup base",
            ability="cleanup",
            required_tags=("trim", "lower"),
            unit_cases=cleanup_request().unit_cases,
            shadow_cases=cleanup_request().shadow_cases,
        )
        self.assertTrue(decision.promoted)
        variants = SkillEvolution(bindings).mutate(
            spec,
            max_variants=6,
        )
        self.assertTrue(variants)
        self.assertTrue(
            all(
                all(
                    bindings.is_eligible(node.binding_id)
                    for node in variant.candidate.nodes
                )
                for variant in variants
            )
        )
        self.assertTrue(
            all(
                variant.candidate.skill_id != spec.skill_id
                for variant in variants
            )
        )

    def test_deployment_refuses_skill_before_local_promotion(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        spec = factory.inventor.invent(
            name="candidate only",
            ability="cleanup",
            required_tags=("trim", "lower"),
        )
        factory.registry.add_candidate(spec)
        deployment = VerifiedSkillDeployment(factory)
        with self.assertRaisesRegex(ValueError, "locally active"):
            deployment.stage(spec.skill_id, evidence_id="not-active")

    def test_proposal_for_wrong_ability_cannot_be_deployed(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup", "other"])
        evaluator = FAPEval(
            (EvalCase("c1", "cleanup", " A ", "a"),)
        )
        core = AutonomousImprovementCore(
            ability_map=amap,
            factory=factory,
            evaluator=evaluator,
        )
        wrong = SkillBuildRequest(
            "other",
            "wrong",
            ("trim",),
            0.5,
            (
                SkillTestCase(" A ", "A"),
                SkillTestCase(" B ", "B"),
                SkillTestCase(" ", "", boundary=True),
            ),
            (
                SkillTestCase(" C ", "C"),
                SkillTestCase(" D ", "D"),
                SkillTestCase(" E ", "E"),
            ),
        )
        result = core.cycle(
            cycle_id="wrong-ability",
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda *args: wrong,
            max_repairs=1,
        )
        self.assertFalse(result.globally_accepted)
        self.assertEqual(result.reason, "proposal_ability_mismatch")
        self.assertEqual(result.locally_promoted_skills, ())

    def test_failed_global_eval_updates_capability_map_from_final_state_only(self):
        bindings = bindings_for_cleanup()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup"])
        evaluator = FAPEval(
            (EvalCase("c1", "cleanup", " A ", "a", 0.7),)
        )
        core = AutonomousImprovementCore(
            ability_map=amap,
            factory=factory,
            evaluator=evaluator,
        )
        result = core.cycle(
            cycle_id="no-proposal",
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda *args: None,
        )
        self.assertFalse(result.globally_accepted)
        state = result.scorecard["cleanup"]
        self.assertEqual(state["attempts"], 1)
        self.assertEqual(state["successes"], 0)
        self.assertEqual(state["frontier"], 0.25)


if __name__ == "__main__":
    unittest.main()
