from __future__ import annotations

from pathlib import Path
from typing import Optional

from .engine import (
    AbilityMap,
    AbilityState,
    AttemptResult,
    CurriculumGenerator,
    CurriculumTask,
    PatternStore,
    SelfCurriculumEngine,
    SuccessPattern,
    VerificationResult,
)


PRIMITIVE_ABILITIES = (
    "string_normalization",
    "numeric_transform",
    "list_transform",
)


class PrimitiveExerciseGenerator(CurriculumGenerator):
    """Creates bounded practice that V80 Mini-IR can independently verify."""

    def generate(
        self,
        state: AbilityState,
        patterns: list[SuccessPattern],
    ) -> CurriculumTask:
        self.counter += 1
        difficulty = self.next_difficulty(state)
        n = self.counter

        if state.ability == "string_normalization":
            composite = difficulty >= 0.40
            if composite:
                examples = [
                    {"value": "  HELLO  ", "expected": "hello"},
                    {
                        "value": f" World{n} ",
                        "expected": f"world{n}",
                    },
                    {"value": "  FAP", "expected": "fap"},
                    {"value": "MiXeD  ", "expected": "mixed"},
                    {
                        "value": "   ",
                        "expected": "",
                        "boundary": True,
                    },
                ]
                holdouts = [
                    {
                        "value": f" ALPHA{n} ",
                        "expected": f"alpha{n}",
                    },
                    {"value": "Beta  ", "expected": "beta"},
                    {"value": " GAMMA ", "expected": "gamma"},
                ]
                target = "strip+lower"
            else:
                examples = [
                    {"value": "  HELLO  ", "expected": "HELLO"},
                    {
                        "value": f" World{n} ",
                        "expected": f"World{n}",
                    },
                    {"value": "  FAP", "expected": "FAP"},
                    {"value": "MiXeD  ", "expected": "MiXeD"},
                    {
                        "value": "   ",
                        "expected": "",
                        "boundary": True,
                    },
                ]
                holdouts = [
                    {
                        "value": f" ALPHA{n} ",
                        "expected": f"ALPHA{n}",
                    },
                    {"value": "Beta  ", "expected": "Beta"},
                    {"value": " GAMMA ", "expected": "GAMMA"},
                ]
                target = "strip"
            payload = {
                "input_kind": "string",
                "target": target,
                "examples": examples,
                "holdouts": holdouts,
            }

        elif state.ability == "numeric_transform":
            delta = 2 + (n % 5)
            examples = [
                {"value": -7, "expected": -7 + delta},
                {"value": -1, "expected": -1 + delta},
                {
                    "value": 0,
                    "expected": delta,
                    "boundary": True,
                },
                {"value": 3, "expected": 3 + delta},
                {"value": 11, "expected": 11 + delta},
            ]
            holdouts = [
                {"value": -20, "expected": -20 + delta},
                {"value": 8, "expected": 8 + delta},
                {"value": 42, "expected": 42 + delta},
            ]
            payload = {
                "input_kind": "number",
                "target": f"add:{delta}",
                "examples": examples,
                "holdouts": holdouts,
            }

        elif state.ability == "list_transform":
            reverse = difficulty >= 0.45
            if reverse:
                examples = [
                    {
                        "value": [1, 2, 3],
                        "expected": [3, 2, 1],
                    },
                    {
                        "value": ["a", "b"],
                        "expected": ["b", "a"],
                    },
                    {
                        "value": [True, False],
                        "expected": [False, True],
                    },
                    {"value": [1], "expected": [1]},
                    {
                        "value": [],
                        "expected": [],
                        "boundary": True,
                    },
                ]
                holdouts = [
                    {
                        "value": [4, 5, 6, 7],
                        "expected": [7, 6, 5, 4],
                    },
                    {
                        "value": ["x", "y", "z"],
                        "expected": ["z", "y", "x"],
                    },
                    {
                        "value": [0, 1],
                        "expected": [1, 0],
                    },
                ]
                target = "reverse"
            else:
                examples = [
                    {
                        "value": [1, 1, 2],
                        "expected": [1, 2],
                    },
                    {
                        "value": ["a", "a"],
                        "expected": ["a"],
                    },
                    {
                        "value": [1, 2, 1],
                        "expected": [1, 2],
                    },
                    {
                        "value": [True, True, False],
                        "expected": [True, False],
                    },
                    {
                        "value": [],
                        "expected": [],
                        "boundary": True,
                    },
                ]
                holdouts = [
                    {
                        "value": [3, 3, 4],
                        "expected": [3, 4],
                    },
                    {
                        "value": ["x", "x", "y"],
                        "expected": ["x", "y"],
                    },
                    {
                        "value": [0, 0],
                        "expected": [0],
                    },
                ]
                target = "unique"
            payload = {
                "input_kind": "list",
                "target": target,
                "examples": examples,
                "holdouts": holdouts,
            }
        else:
            raise ValueError(
                "unsupported primitive curriculum ability: "
                + state.ability
            )

        prior = (
            patterns[0].summary
            if patterns
            else "none"
        )
        prompt = (
            f"Invent a safe Mini-IR primitive for {state.ability}; "
            f"target={payload['target']}; "
            f"difficulty={difficulty:.2f}; "
            f"reuse prior only if it generalizes: {prior}"
        )
        return CurriculumTask(
            task_id=(
                f"primitive-self:"
                f"{state.ability}:{self.counter}"
            ),
            ability=state.ability,
            prompt=prompt,
            difficulty=round(difficulty, 4),
            parent_pattern_id=(
                patterns[0].pattern_id
                if patterns
                else ""
            ),
            novelty=round(
                1.0 if not patterns else 0.7,
                4,
            ),
            payload=payload,
        )


class PrimitiveSelfCurriculum:
    """Concrete V82 bridge to V80 Inventor -> Sandbox -> Registry."""

    def __init__(
        self,
        *,
        ability_map_path: Optional[str | Path] = None,
        pattern_store_path: Optional[str | Path] = None,
        registry_path: Optional[str | Path] = None,
        stretch: float = 0.10,
        timeout_ms: float = 50.0,
    ):
        from fap_creativity.primitive_invention import (
            MiniIRSandbox,
            PrimitiveInventor,
            PrimitivePromotionLoop,
            PrimitiveTestCase,
            SkillRegistry,
        )

        self._PrimitiveTestCase = PrimitiveTestCase
        self.sandbox = MiniIRSandbox(
            timeout_ms=timeout_ms
        )
        self.inventor = PrimitiveInventor(self.sandbox)
        self.registry = SkillRegistry(registry_path)
        self.promotion = PrimitivePromotionLoop(
            sandbox=self.sandbox,
            registry=self.registry,
        )
        self._candidates = {}
        self.generator = PrimitiveExerciseGenerator(
            stretch=stretch
        )
        self.engine = SelfCurriculumEngine(
            PRIMITIVE_ABILITIES,
            solver=self._solve,
            verifier=self._verify,
            generator=self.generator,
            store=PatternStore(pattern_store_path),
            ability_map=AbilityMap(
                PRIMITIVE_ABILITIES,
                ability_map_path,
            ),
        )

    def _case(self, raw):
        return self._PrimitiveTestCase(
            value=raw["value"],
            expected=raw["expected"],
            boundary=bool(
                raw.get("boundary", False)
            ),
            label=str(raw.get("label", "")),
        )

    def _solve(
        self,
        task: CurriculumTask,
        priors: list[SuccessPattern],
    ):
        examples = tuple(
            self._case(x)
            for x in task.payload["examples"]
        )
        candidate = self.inventor.invent_from_examples(
            name=f"self_{task.ability}",
            input_kind=str(
                task.payload["input_kind"]
            ),
            examples=examples,
            description=task.prompt,
            max_depth=2,
        )
        self._candidates[task.task_id] = candidate
        program = [
            ins.op for ins in candidate.program
        ]
        return AttemptResult(
            answer=(
                f"{task.ability} "
                + " -> ".join(program)
            ),
            evidence={
                "candidate_id": candidate.primitive_id,
                "program": program,
                "target": task.payload["target"],
            },
        )

    def _verify(
        self,
        task: CurriculumTask,
        attempt: AttemptResult,
    ):
        candidate = self._candidates[task.task_id]
        holdouts = tuple(
            self._case(x)
            for x in task.payload["holdouts"]
        )
        decision = self.promotion.evaluate(
            candidate,
            shadow_cases=holdouts,
        )
        if (
            decision.promoted
            and decision.stage == "active"
        ):
            reward = 1.0
        elif decision.stage == "shadow":
            reward = 0.55
        else:
            reward = 0.0
        return VerificationResult(
            passed=bool(decision.promoted),
            reward=reward,
            reason=(
                f"v80_sandbox:{decision.stage};"
                f"unit={decision.unit_passed}/"
                f"{decision.unit_total};"
                f"shadow={decision.shadow_successes}"
            ),
            independent=True,
        )

    def dream(self, steps: int = 1):
        return self.engine.run(steps)

    def capability_map(self):
        return self.engine.ability_map.snapshot()

    def active_primitives(self):
        return self.registry.active()


def build_primitive_self_curriculum(
    **kwargs,
) -> PrimitiveSelfCurriculum:
    return PrimitiveSelfCurriculum(**kwargs)
