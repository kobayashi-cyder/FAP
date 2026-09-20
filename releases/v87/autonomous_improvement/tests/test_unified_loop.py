from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
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
    CycleEvidenceStore,
    EvalCase,
    FAPEval,
    RepairRecipe,
    UnifiedSelfImprovementLoop,
)
from fap_generic_skill import (
    AdaptiveSkillGraphBridge,
    BindingRegistry,
    GenericSkillFactory,
    SkillBinding,
    SkillTestCase,
)
from fap_self_curriculum import AbilityMap, PatternStore


REQUIRED_EVIDENCE = {
    "input_state",
    "capability_map_before",
    "selected_weakness",
    "generated_task",
    "router_trace",
    "candidate_skill",
    "sandbox_result",
    "verifier_result",
    "promotion_or_rejection_decision",
    "memory_record",
    "capability_map_after",
}


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
    return bindings


def uppercase_cases():
    unit = (
        SkillTestCase(" a ", "A"),
        SkillTestCase(" b ", "B"),
        SkillTestCase(" c ", "C"),
        SkillTestCase("", "", boundary=True),
    )
    shadow = (
        SkillTestCase(" d ", "D"),
        SkillTestCase(" e ", "E"),
        SkillTestCase(" f ", "F"),
    )
    return unit, shadow


def trim_cases():
    unit = (
        SkillTestCase(" a ", "a"),
        SkillTestCase(" b ", "b"),
        SkillTestCase(" c ", "c"),
        SkillTestCase("", "", boundary=True),
    )
    shadow = (
        SkillTestCase(" d ", "d"),
        SkillTestCase(" e ", "e"),
        SkillTestCase(" f ", "f"),
    )
    return unit, shadow


def evaluator():
    return FAPEval(
        (
            EvalCase("u1", "text_normalization", " a ", "A"),
            EvalCase("u2", "text_normalization", " b ", "B"),
            EvalCase("u3", "text_normalization", " c ", "C"),
        )
    )


class UnifiedSelfImprovementLoopTests(unittest.TestCase):
    def test_complete_autonomous_cycle_improves_persists_and_routes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindings = make_bindings()
            factory = GenericSkillFactory(
                bindings,
                registry_path=root / "skills.json",
            )
            ability_map = AbilityMap(
                ["text_normalization"],
                root / "ability.json",
            )
            bridge = AdaptiveSkillGraphBridge(factory.graph, bindings)
            core = AutonomousImprovementCore(
                ability_map=ability_map,
                factory=factory,
                evaluator=evaluator(),
                adaptive_bridge=bridge,
            )
            unit, shadow = uppercase_cases()
            evidence_store = CycleEvidenceStore(root / "cycles.json")
            loop = UnifiedSelfImprovementLoop(
                core=core,
                fallback_solver=lambda case: case.payload,
                repair_recipes={
                    "text_normalization": RepairRecipe(
                        ability="text_normalization",
                        name="auto_normalize_upper",
                        required_tags=("trim", "upper"),
                        unit_cases=unit,
                        shadow_cases=shadow,
                    )
                },
                evidence_store=evidence_store,
                pattern_store=PatternStore(root / "patterns.json"),
            )

            result = loop.run(input_state={"source": "unit-test"})

            self.assertTrue(result.accepted)
            self.assertEqual(result.selected_weakness, "text_normalization")
            self.assertEqual(result.before_accuracy, 0.0)
            self.assertEqual(result.trial_accuracy, 1.0)
            self.assertEqual(result.after_accuracy, 1.0)
            self.assertIn(result.candidate_skill_id, result.routed_skill_ids)
            self.assertTrue(result.memory_persisted)

            record = evidence_store.records[-1]
            self.assertTrue(REQUIRED_EVIDENCE.issubset(record))
            self.assertEqual(
                record["promotion_or_rejection_decision"]["action"],
                "PROMOTED",
            )
            self.assertEqual(
                record["router_trace"]["selected"][0]["circuit_id"],
                result.candidate_skill_id,
            )
            self.assertIn(
                result.candidate_skill_id,
                record["memory_record"]["active_memory"],
            )
            self.assertTrue(
                record["memory_record"]["compressed_success"]["stored"]
            )
            self.assertGreater(
                record["evaluation"]["target_after"],
                record["evaluation"]["target_before"],
            )

            # Restart from persistent verifier/skill/evidence state.
            bindings2 = make_bindings()
            factory2 = GenericSkillFactory(
                bindings2,
                registry_path=root / "skills.json",
            )
            core2 = AutonomousImprovementCore(
                ability_map=AbilityMap(
                    ["text_normalization"],
                    root / "ability.json",
                ),
                factory=factory2,
                evaluator=evaluator(),
                adaptive_bridge=AdaptiveSkillGraphBridge(
                    factory2.graph,
                    bindings2,
                ),
            )
            restored = UnifiedSelfImprovementLoop(
                core=core2,
                fallback_solver=lambda case: case.payload,
                repair_recipes={},
                evidence_store=CycleEvidenceStore(root / "cycles.json"),
                pattern_store=PatternStore(root / "patterns.json"),
            )
            self.assertIn(
                result.candidate_skill_id,
                restored.core.adopted_skill_ids,
            )
            self.assertEqual(
                restored.evidence_store.records[-1]["evidence_id"],
                result.evidence_id,
            )

    def test_non_improving_candidate_is_rejected_and_never_routed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindings = make_bindings()
            factory = GenericSkillFactory(
                bindings,
                registry_path=root / "skills.json",
            )
            bridge = AdaptiveSkillGraphBridge(factory.graph, bindings)
            core = AutonomousImprovementCore(
                ability_map=AbilityMap(
                    ["text_normalization"],
                    root / "ability.json",
                ),
                factory=factory,
                evaluator=evaluator(),
                adaptive_bridge=bridge,
            )
            unit, shadow = trim_cases()
            evidence_store = CycleEvidenceStore(root / "cycles.json")
            loop = UnifiedSelfImprovementLoop(
                core=core,
                fallback_solver=lambda case: case.payload,
                repair_recipes={
                    "text_normalization": RepairRecipe(
                        ability="text_normalization",
                        name="wrong_semantics_trim",
                        required_tags=("trim",),
                        unit_cases=unit,
                        shadow_cases=shadow,
                    )
                },
                evidence_store=evidence_store,
                pattern_store=PatternStore(root / "patterns.json"),
            )

            result = loop.run(input_state={"source": "negative-test"})

            self.assertFalse(result.accepted)
            self.assertEqual(result.before_accuracy, 0.0)
            self.assertEqual(result.trial_accuracy, 0.0)
            self.assertEqual(result.after_accuracy, 0.0)
            self.assertIn(
                result.candidate_skill_id,
                core.quarantined_skill_ids,
            )
            self.assertNotIn(
                result.candidate_skill_id,
                core.adopted_skill_ids,
            )
            routed = bridge.route(
                "text_normalization trim",
                allowed_skill_ids=set(core.adopted_skill_ids),
            )
            self.assertEqual(routed.circuit_ids, ())

            record = evidence_store.records[-1]
            self.assertEqual(
                record["promotion_or_rejection_decision"]["action"],
                "REJECTED",
            )
            self.assertEqual(
                record["promotion_or_rejection_decision"]["reason"],
                "no_measurable_target_improvement",
            )
            self.assertTrue(record["verifier_result"]["promoted"])
            self.assertEqual(record["router_trace"]["selected"], [])
            self.assertTrue((root / "cycles.json").is_file())


if __name__ == "__main__":
    unittest.main()
