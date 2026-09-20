from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional

from .engine import (
    AbilityMap,
    AttemptResult,
    CurriculumGenerator,
    CurriculumTask,
    PatternStore,
    SelfCurriculumEngine,
    SuccessPattern,
    VerificationResult,
)

DEFAULT_ABILITIES = (
    "decomposition",
    "composition",
    "generalization",
    "verification",
    "repair",
    "creative_transfer",
)


class FAPSelfCurriculum:
    """Generic facade for attaching the V82 curriculum policy to FAP."""

    def __init__(
        self,
        *,
        solver: Callable[
            [CurriculumTask, list[SuccessPattern]],
            AttemptResult | str,
        ],
        verifier: Callable[
            [CurriculumTask, AttemptResult],
            VerificationResult,
        ],
        abilities: Iterable[str] = DEFAULT_ABILITIES,
        ability_map_path: Optional[str | Path] = None,
        store_path: Optional[str | Path] = None,
        stretch: float = 0.10,
        generator: Optional[CurriculumGenerator] = None,
    ):
        self.engine = SelfCurriculumEngine(
            abilities,
            solver=solver,
            verifier=verifier,
            generator=(
                generator
                or CurriculumGenerator(stretch=stretch)
            ),
            store=PatternStore(store_path),
            ability_map=AbilityMap(
                abilities,
                ability_map_path,
            ),
        )

    def dream(self, steps: int = 1):
        return self.engine.run(steps)

    def capability_map(self):
        return self.engine.ability_map.snapshot()

    def compressed_successes(
        self,
        ability: str,
        limit: int = 3,
    ):
        return self.engine.store.for_ability(
            ability,
            limit,
        )


def build_v82_curriculum(
    *,
    solver: Callable[
        [CurriculumTask, list[SuccessPattern]],
        AttemptResult | str,
    ],
    verifier: Callable[
        [CurriculumTask, AttemptResult],
        VerificationResult,
    ],
    abilities: Iterable[str] = DEFAULT_ABILITIES,
    ability_map_path: Optional[str | Path] = None,
    store_path: Optional[str | Path] = None,
    stretch: float = 0.10,
    generator: Optional[CurriculumGenerator] = None,
) -> FAPSelfCurriculum:
    return FAPSelfCurriculum(
        solver=solver,
        verifier=verifier,
        abilities=abilities,
        ability_map_path=ability_map_path,
        store_path=store_path,
        stretch=stretch,
        generator=generator,
    )
