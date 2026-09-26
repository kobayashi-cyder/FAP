from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
V86_ROOT = ROOT.parents[1] / "v86" / "generic_skill_factory"
V84_ROOT = ROOT.parents[1] / "v84" / "self_curriculum"
V82_ROOT = ROOT.parents[1] / "v82" / "adaptive_circuits"
sys.path.insert(0, str(V86_ROOT))
sys.path.insert(0, str(V84_ROOT))
sys.path.insert(0, str(V82_ROOT))
sys.path.insert(0, str(ROOT))

from fap_autonomous_improvement import (
    AutonomousImprovementCore,
    EvalCase,
    FAPEval,
    RepairProposal,
    SOURCE_V90_SHA256,
    SkillEvolution,
)
from fap_generic_skill import (
    AdaptiveSkillGraphBridge,
    BindingRegistry,
    GenericSkillFactory,
    SkillBinding,
    SkillTestCase,
)
from fap_self_curriculum import AbilityMap


def make_bindings():
    bindings = BindingRegistry()
    bindings.register(
        SkillBinding(
            "text.trim",
            lambda value: value.strip(),
            ("trim", "cleanup", "text"),
        )
    )
    bindings.register(
        SkillBinding(
            "text.upper",
            lambda value: value.upper(),
            ("upper", "case", "text"),
        )
    )
    bindings.register(
        SkillBinding(
            "text.lower",
            lambda value: value.lower(),
            ("lower", "case", "text"),
        )
    )
    bindings.register(
        SkillBinding(
            "text.trim.alt",
            lambda value: value.strip(),
            ("trim", "cleanup", "text"),
        )
    )
    return bindings


def uppercase_cases():
    unit = (
        SkillTestCase(" a ", "A"),
        SkillTestCase(" b ", "B"),
        SkillTestCase(" c ", "C"),
        SkillTestCase(" x ", "X"),
        SkillTestCase("", "", boundary=True),
    )
    shadow = (
        SkillTestCase(" d ", "D"),
        SkillTestCase(" e ", "E"),
        SkillTestCase(" f ", "F"),
    )
    return unit, shadow


class V87AutonomousImprovementTests(unittest.TestCase):
    def test_source_v90_provenance_is_anchored(self):
        self.assertEqual(
            SOURCE_V90_SHA256,
            "660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7",
        )

    def test_fap_eval_clusters_failures(self):
        evaluator = FAPEval(
            (
                EvalCase("a1", "a", 1, 2),
                EvalCase("a2", "a", 2, 3),
                EvalCase("b1", "b", 4, 4),
            )
        )
        result = evaluator.run(lambda case: case.payload)
        self.assertEqual(result.passed, 1)
        clusters = evaluator.failure_clusters(result)
        self.assertEqual(len(clusters["a"]), 2)
        self.assertNotIn("b", clusters)

    def test_skill_evolution_mutates_only_verified_binding_ids(self):
        factory = GenericSkillFactory(make_bindings())
        unit, shadow = uppercase_cases()
        parent, decision = factory.invent_and_promote(
            name="normalize_upper",
            ability="text_normalization",
            required_tags=("trim", "upper"),
            unit_cases=unit,
            shadow_cases=shadow,
        )
        self.assertTrue(decision.promoted)
        variants = SkillEvolution(factory).mutate(parent, max_variants=4)
        self.assertTrue(variants)
        self.assertTrue(all(v.parent_skill_id == parent.skill_id for v in variants))
        eligible = set(factory.bindings.bindings)
        self.assertTrue(
            all(
                node.binding_id in eligible
                for variant in variants
                for node in variant.candidate.nodes
            )
        )
        self.assertTrue(all(not hasattr(v.candidate, "source") for v in variants))

    def test_autonomous_cycle_repairs_failure_cluster_and_adopts(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        bridge = AdaptiveSkillGraphBridge(factory.graph, bindings)
        evaluator = FAPEval(
            (
                EvalCase("u1", "text_normalization", " a ", "A"),
                EvalCase("u2", "text_normalization", " b ", "B"),
                EvalCase("u3", "text_normalization", " c ", "C"),
            )
        )
        ability_map = AbilityMap(["text_normalization"])
        core = AutonomousImprovementCore(
            ability_map=ability_map,
            factory=factory,
            evaluator=evaluator,
            adaptive_bridge=bridge,
        )
        unit, shadow = uppercase_cases()

        def provider(ability, failures):
            return RepairProposal(
                ability=ability,
                name="auto_normalize_upper",
                required_tags=("trim", "upper"),
                difficulty=0.6,
                unit_cases=unit,
                shadow_cases=shadow,
            )

        result = core.cycle(
            fallback_solver=lambda case: case.payload,
            proposal_provider=provider,
        )
        self.assertEqual(result.before_accuracy, 0.0)
        self.assertEqual(result.trial_accuracy, 1.0)
        self.assertEqual(result.after_accuracy, 1.0)
        self.assertTrue(result.accepted)
        self.assertFalse(result.regressed)
        self.assertEqual(result.remaining_failures, 0)
        self.assertEqual(len(result.adopted_skills), 1)
        routed = bridge.route("text_normalization cleanup upper")
        self.assertIn(result.adopted_skills[0], routed.circuit_ids)

    def test_promoted_but_non_improving_skill_is_quarantined(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        evaluator = FAPEval(
            (
                EvalCase("u1", "text_normalization", " a ", "A"),
                EvalCase("u2", "text_normalization", " b ", "B"),
            )
        )
        core = AutonomousImprovementCore(
            ability_map=AbilityMap(["text_normalization"]),
            factory=factory,
            evaluator=evaluator,
        )
        trim_unit = (
            SkillTestCase(" a ", "a"),
            SkillTestCase(" b ", "b"),
            SkillTestCase(" c ", "c"),
            SkillTestCase(" x ", "x"),
            SkillTestCase("", "", boundary=True),
        )
        trim_shadow = (
            SkillTestCase(" d ", "d"),
            SkillTestCase(" e ", "e"),
            SkillTestCase(" f ", "f"),
        )

        result = core.cycle(
            fallback_solver=lambda case: case.payload,
            proposal_provider=lambda ability, failures: RepairProposal(
                ability,
                "wrong_semantics_trim",
                ("trim",),
                0.6,
                trim_unit,
                trim_shadow,
            ),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.before_accuracy, 0.0)
        self.assertEqual(result.trial_accuracy, 0.0)
        self.assertEqual(result.after_accuracy, 0.0)
        self.assertEqual(len(result.quarantined_skills), 1)
        self.assertFalse(core.adopted_skill_ids)

    def test_existing_adopted_skill_is_used_before_fallback(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        unit, shadow = uppercase_cases()
        skill, decision = factory.invent_and_promote(
            name="known",
            ability="text_normalization",
            required_tags=("trim", "upper"),
            unit_cases=unit,
            shadow_cases=shadow,
        )
        self.assertTrue(decision.promoted)
        core = AutonomousImprovementCore(
            ability_map=AbilityMap(["text_normalization"]),
            factory=factory,
            evaluator=FAPEval(
                (EvalCase("u1", "text_normalization", " a ", "A"),)
            ),
        )
        core.adopted_skill_ids.add(skill.skill_id)
        result = core.cycle(
            fallback_solver=lambda case: "WRONG",
            proposal_provider=lambda ability, failures: None,
        )
        self.assertEqual(result.before_accuracy, 1.0)
        self.assertEqual(result.after_accuracy, 1.0)
        self.assertEqual(result.target_ability, "")


if __name__ == "__main__":
    unittest.main()
