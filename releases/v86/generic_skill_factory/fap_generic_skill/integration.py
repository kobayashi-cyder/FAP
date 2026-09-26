from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .core import (
    GenericSkillFactory,
    PromotionDecision,
    SkillSpec,
    SkillTestCase,
)


@dataclass(frozen=True)
class SkillBuildRequest:
    ability: str
    name: str
    required_tags: tuple[str, ...]
    difficulty: float
    unit_cases: tuple[SkillTestCase, ...]
    shadow_cases: tuple[SkillTestCase, ...]


class CapabilitySkillFactoryBridge:
    """V84 capability weakness -> V86 invented Skill -> independent promotion."""

    def __init__(self, ability_map, factory: GenericSkillFactory):
        self.ability_map = ability_map
        self.factory = factory

    def build(self, request: SkillBuildRequest) -> tuple[SkillSpec, PromotionDecision]:
        from fap_self_curriculum.engine import VerificationResult

        spec, decision = self.factory.invent_and_promote(
            name=request.name,
            ability=request.ability,
            required_tags=request.required_tags,
            unit_cases=request.unit_cases,
            shadow_cases=request.shadow_cases,
        )
        verification = VerificationResult(
            passed=decision.promoted and decision.stage == "active",
            reward=1.0 if decision.promoted else 0.0,
            reason=f"v86_skill_factory:{decision.reason}",
            independent=True,
        )
        self.ability_map.update(
            request.ability,
            request.difficulty,
            verification,
        )
        return spec, decision

    def build_for_weakest(
        self,
        requests: Mapping[str, SkillBuildRequest],
    ) -> tuple[SkillSpec, PromotionDecision]:
        focus = self.ability_map.choose_focus().ability
        if focus not in requests:
            raise KeyError(f"no V86 build request for weak capability: {focus}")
        return self.build(requests[focus])
