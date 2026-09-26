from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from fap_media_generation import Critique, CritiqueIssue


@dataclass(frozen=True)
class CriticStage:
    name: str
    critic: Any
    continue_floor: float = 0.0

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("stage name required")
        if not callable(getattr(self.critic, "critique", None)):
            raise TypeError("stage critic must provide critique()")
        if not (0.0 <= self.continue_floor <= 1.0):
            raise ValueError("continue_floor out of bounds")


class CascadeCritic:
    """Run cheap critics first and expensive critics only when useful.

    Acceptance remains strict: when every early stage passes its continue floor,
    all configured stages are evaluated and the minimum score is returned.

    Rejection can short-circuit: a fatal issue or sufficiently low early score
    stops later stages because the artifact cannot pass the final gate anyway.
    """

    def __init__(self, stages: Sequence[CriticStage]):
        if not stages:
            raise ValueError("at least one critic stage required")
        seen: set[str] = set()
        normalized = []
        for stage in stages:
            stage.validate()
            if stage.name in seen:
                raise ValueError("duplicate stage name")
            seen.add(stage.name)
            normalized.append(stage)
        self.stages = tuple(normalized)

    def critique(self, request, artifact) -> Critique:
        all_issues = []
        evidence = {}
        minimum_score = 1.0
        evaluated = []
        skipped = []

        for index, stage in enumerate(self.stages):
            result = stage.critic.critique(request, artifact)
            if not isinstance(result, Critique):
                raise TypeError("stage critic must return Critique")
            result.validate()
            evaluated.append(stage.name)
            evidence[stage.name] = dict(result.evidence)
            all_issues.extend(result.issues)
            minimum_score = min(minimum_score, float(result.score))

            if result.has_fatal:
                skipped = [s.name for s in self.stages[index + 1 :]]
                evidence["cascade"] = {
                    "evaluated": tuple(evaluated),
                    "skipped": tuple(skipped),
                    "stop": "fatal",
                }
                return Critique(0.0, tuple(all_issues), evidence=evidence)

            if result.score < stage.continue_floor:
                skipped = [s.name for s in self.stages[index + 1 :]]
                if not result.issues:
                    all_issues.append(
                        CritiqueIssue(
                            f"cascade_{stage.name}",
                            f"{stage.name} score {result.score:.3f} below continue floor {stage.continue_floor:.3f}",
                            "medium",
                            f"repair defects detected by {stage.name} before expensive evaluation",
                        )
                    )
                evidence["cascade"] = {
                    "evaluated": tuple(evaluated),
                    "skipped": tuple(skipped),
                    "stop": "below_continue_floor",
                }
                return Critique(minimum_score, tuple(all_issues), evidence=evidence)

        evidence["cascade"] = {
            "evaluated": tuple(evaluated),
            "skipped": (),
            "stop": "complete",
        }
        return Critique(minimum_score, tuple(all_issues), evidence=evidence)
