from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
V84_ROOT = ROOT.parents[1] / "v84" / "self_curriculum"
V82_ROOT = ROOT.parents[1] / "v82" / "adaptive_circuits"
sys.path.insert(0, str(V84_ROOT))
sys.path.insert(0, str(V82_ROOT))
sys.path.insert(0, str(ROOT))

from fap_adaptive_circuits import AdaptiveCircuitController
from fap_self_curriculum import AbilityMap
from fap_generic_skill import (
    AdaptiveSkillGraphBridge,
    BindingRegistry,
    CapabilitySkillFactoryBridge,
    GenericSkillFactory,
    SkillBinding,
    SkillBuildRequest,
    SkillEdge,
    SkillGraphValidator,
    SkillNode,
    SkillRegistry,
    SkillSandbox,
    SkillSpec,
    SkillTestCase,
)


def make_bindings() -> BindingRegistry:
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


def unit_cases():
    return (
        SkillTestCase(" A ", "a"),
        SkillTestCase("  Hello  ", "hello"),
        SkillTestCase("   ", "", boundary=True),
    )


def shadow_cases():
    return (
        SkillTestCase(" B ", "b"),
        SkillTestCase("\tMixed CASE\n", "mixed case"),
        SkillTestCase(" Z  ", "z"),
    )


class V86GenericSkillFactoryTests(unittest.TestCase):
    def test_inventor_composes_verified_bindings_into_dag(self):
        factory = GenericSkillFactory(make_bindings())
        spec = factory.inventor.invent(
            name="trim then lower",
            ability="cleanup",
            required_tags=("trim", "lower"),
        )
        self.assertEqual(
            [node.binding_id for node in spec.nodes],
            ["text.trim", "text.lower"],
        )
        self.assertEqual(
            [(edge.source, edge.target) for edge in spec.edges],
            [("n0", "n1")],
        )
        self.assertEqual(
            SkillGraphValidator.topological(spec),
            ("n0", "n1"),
        )

    def test_unverified_binding_cannot_be_invented_into_skill(self):
        bindings = BindingRegistry()
        bindings.register(
            SkillBinding(
                "unsafe.unverified",
                lambda value: value,
                ("needed",),
                verified=False,
            )
        )
        factory = GenericSkillFactory(bindings)
        with self.assertRaisesRegex(ValueError, "no verified binding"):
            factory.inventor.invent(
                name="blocked",
                ability="blocked",
                required_tags=("needed",),
            )

    def test_sandbox_refuses_ineligible_binding_even_for_valid_graph(self):
        bindings = BindingRegistry()
        bindings.register(
            SkillBinding(
                "side.effect",
                lambda value: value,
                ("identity",),
                side_effect_free=False,
            )
        )
        spec = SkillSpec.create(
            name="not safe",
            ability="identity",
            tags=("identity",),
            nodes=(SkillNode("n0", "side.effect"),),
            edges=(),
            output_node="n0",
        )
        result = SkillSandbox(bindings).execute(spec, "x")
        self.assertFalse(result.ok)
        self.assertIn("unverified skill binding", result.error)

    def test_cycle_is_rejected(self):
        spec = SkillSpec(
            "skill:fake",
            "cycle",
            "cycle",
            ("cycle",),
            (
                SkillNode("a", "text.trim"),
                SkillNode("b", "text.lower"),
            ),
            (
                SkillEdge("a", "b"),
                SkillEdge("b", "a"),
            ),
            "b",
        )
        with self.assertRaisesRegex(ValueError, "acyclic"):
            SkillGraphValidator.validate(spec)

    def test_verified_candidate_promotes_and_generic_graph_executes(self):
        factory = GenericSkillFactory(make_bindings())
        spec, decision = factory.invent_and_promote(
            name="trim lower",
            ability="cleanup",
            required_tags=("trim", "lower"),
            unit_cases=unit_cases(),
            shadow_cases=shadow_cases(),
        )
        self.assertTrue(decision.promoted)
        self.assertEqual(decision.stage, "active")
        result = factory.graph.execute(spec.skill_id, "  TeSt ")
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "test")
        manifest = factory.graph.manifest()
        self.assertFalse(manifest["generated_code_allowed"])
        self.assertEqual(
            manifest["active_skills"][0]["skill_id"],
            spec.skill_id,
        )

    def test_failed_unit_case_is_rejected_not_promoted(self):
        factory = GenericSkillFactory(make_bindings())
        bad_cases = (
            SkillTestCase(" A ", "WRONG"),
            SkillTestCase(" B ", "b"),
            SkillTestCase(" ", "", boundary=True),
        )
        _, decision = factory.invent_and_promote(
            name="bad candidate",
            ability="cleanup",
            required_tags=("trim", "lower"),
            unit_cases=bad_cases,
            shadow_cases=shadow_cases(),
        )
        self.assertFalse(decision.promoted)
        self.assertEqual(decision.stage, "rejected")

    def test_active_registry_round_trip_requires_same_verified_bindings(self):
        bindings = make_bindings()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "skills.json"
            factory = GenericSkillFactory(
                bindings,
                registry_path=path,
            )
            spec, decision = factory.invent_and_promote(
                name="persistent cleanup",
                ability="cleanup",
                required_tags=("trim", "lower"),
                unit_cases=unit_cases(),
                shadow_cases=shadow_cases(),
            )
            self.assertTrue(decision.promoted)
            loaded = SkillRegistry(path, bindings=bindings)
            self.assertEqual(
                loaded.active()[0]["skill_id"],
                spec.skill_id,
            )
            with self.assertRaisesRegex(ValueError, "binding registry"):
                SkillRegistry(path)

    def test_persisted_skill_digest_tampering_fails_closed(self):
        bindings = make_bindings()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "skills.json"
            factory = GenericSkillFactory(
                bindings,
                registry_path=path,
            )
            factory.invent_and_promote(
                name="persistent cleanup",
                ability="cleanup",
                required_tags=("trim", "lower"),
                unit_cases=unit_cases(),
                shadow_cases=shadow_cases(),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["records"][0]["skill"]["name"] = "tampered skill"
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "identity digest"):
                SkillRegistry(path, bindings=bindings)

    def test_v84_ability_frontier_advances_only_after_active_skill(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup"])
        before = amap.snapshot()["cleanup"]["frontier"]
        bridge = CapabilitySkillFactoryBridge(amap, factory)
        request = SkillBuildRequest(
            "cleanup",
            "curriculum cleanup",
            ("trim", "lower"),
            0.60,
            unit_cases(),
            shadow_cases(),
        )
        _, decision = bridge.build(request)
        self.assertTrue(decision.promoted)
        after = amap.snapshot()["cleanup"]
        self.assertEqual(after["successes"], 1)
        self.assertGreater(after["frontier"], before)

    def test_v84_failed_skill_does_not_advance_frontier(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        amap = AbilityMap(["cleanup"])
        before = amap.snapshot()["cleanup"]["frontier"]
        bridge = CapabilitySkillFactoryBridge(amap, factory)
        request = SkillBuildRequest(
            "cleanup",
            "bad curriculum cleanup",
            ("trim", "lower"),
            0.60,
            (
                SkillTestCase(" A ", "wrong"),
                SkillTestCase(" B ", "b"),
                SkillTestCase(" ", "", boundary=True),
            ),
            shadow_cases(),
        )
        _, decision = bridge.build(request)
        self.assertFalse(decision.promoted)
        after = amap.snapshot()["cleanup"]
        self.assertEqual(after["successes"], 0)
        self.assertEqual(after["frontier"], before)

    def test_v82_sparse_router_executes_only_promoted_generic_skill(self):
        bindings = make_bindings()
        factory = GenericSkillFactory(bindings)
        spec, decision = factory.invent_and_promote(
            name="trim lower",
            ability="cleanup",
            required_tags=("trim", "lower"),
            unit_cases=unit_cases(),
            shadow_cases=shadow_cases(),
        )
        self.assertTrue(decision.promoted)
        controller = AdaptiveCircuitController(
            top_k=2,
            activation_threshold=0.20,
        )
        bridge = AdaptiveSkillGraphBridge(
            factory.graph,
            bindings,
            controller=controller,
        )
        adopted = bridge.sync_active()
        self.assertEqual(adopted, [spec.skill_id])
        route, results = bridge.execute(
            "cleanup trim lower text",
            " A ",
        )
        self.assertEqual(route.circuit_ids, (spec.skill_id,))
        self.assertEqual(results[0].execution.output, "a")
        self.assertTrue(
            bridge.observe(
                route,
                results,
                evidence_id="runtime-1",
            )
        )

    def test_invented_skill_is_declarative_and_contains_no_executable_code_field(self):
        factory = GenericSkillFactory(make_bindings())
        spec = factory.inventor.invent(
            name="declarative",
            ability="cleanup",
            required_tags=("trim", "lower"),
        )
        payload = spec.to_dict()
        encoded = json.dumps(payload, sort_keys=True)
        self.assertNotIn('"code"', encoded)
        self.assertNotIn('"python"', encoded)
        self.assertNotIn('"import"', encoded)
        self.assertEqual(
            set(payload),
            {
                "skill_id",
                "name",
                "ability",
                "tags",
                "nodes",
                "edges",
                "output_node",
            },
        )
        self.assertTrue(
            all(set(node) == {"node_id", "binding_id"} for node in payload["nodes"])
        )
        self.assertTrue(
            all(set(edge) == {"source", "target"} for edge in payload["edges"])
        )


if __name__ == "__main__":
    unittest.main()
