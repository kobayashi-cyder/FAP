from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
V82_ROOT = ROOT.parents[1] / "v82" / "adaptive_circuits"
sys.path.insert(0, str(V82_ROOT))
sys.path.insert(0, str(ROOT))

from fap_generic_skill import (
    AdaptiveSkillGraphBridge,
    BindingRegistry,
    GenericSkillFactory,
    SkillBinding,
    SkillTestCase,
)


class AdaptiveBridgeQuarantineTests(unittest.TestCase):
    def test_blocked_active_skill_stays_out_of_routing_across_resync(self):
        bindings = BindingRegistry()
        bindings.register(
            SkillBinding("text.upper", lambda value: value.upper(), ("upper", "text"))
        )
        factory = GenericSkillFactory(bindings)
        unit = (
            SkillTestCase("a", "A"),
            SkillTestCase("b", "B"),
            SkillTestCase("c", "C"),
            SkillTestCase("", "", boundary=True),
        )
        shadow = (
            SkillTestCase("d", "D"),
            SkillTestCase("e", "E"),
            SkillTestCase("f", "F"),
        )
        skill, decision = factory.invent_and_promote(
            name="uppercase",
            ability="text_normalization",
            required_tags=("upper",),
            unit_cases=unit,
            shadow_cases=shadow,
        )
        self.assertTrue(decision.promoted)

        bridge = AdaptiveSkillGraphBridge(factory.graph, bindings)
        self.assertIn(skill.skill_id, bridge.sync_active())
        self.assertIn(
            skill.skill_id,
            bridge.route("text_normalization upper").circuit_ids,
        )

        bridge.block_skill(skill.skill_id)
        self.assertNotIn(skill.skill_id, bridge.sync_active())
        self.assertNotIn(
            skill.skill_id,
            bridge.route("text_normalization upper").circuit_ids,
        )

        bridge.unblock_skill(skill.skill_id)
        self.assertIn(skill.skill_id, bridge.sync_active())
        self.assertIn(
            skill.skill_id,
            bridge.route("text_normalization upper").circuit_ids,
        )


if __name__ == "__main__":
    unittest.main()
