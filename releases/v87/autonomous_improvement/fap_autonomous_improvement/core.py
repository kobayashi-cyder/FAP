from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from fap_generic_skill import (
    GenericSkillFactory,
    SkillBinding,
    SkillEdge,
    SkillNode,
    SkillSpec,
    SkillTestCase,
)
from fap_self_curriculum import AbilityMap, VerificationResult


SOURCE_V90_ARTIFACT = "FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip"
SOURCE_V90_SHA256 = "660ae75d97cfab478bd54066a1afe4786dba40f07ffd30e0ce7b8c384965a1c7"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    ability: str
    payload: Any
    expected: Any
    evaluator: Callable[[Any, Any], bool] = field(
        default=lambda actual, expected: actual == expected,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True)
class EvalResult:
    total: int
    passed: int
    failed: int
    accuracy: float
    by_ability: Mapping[str, Mapping[str, Any]]
    failures: tuple[Mapping[str, Any], ...]


class FAPEval:
    """Small deterministic benchmark harness derived from the V90 handoff."""

    def __init__(self, cases: Sequence[EvalCase]):
        self.cases = tuple(cases)
        ids = [case.case_id for case in self.cases]
        if not self.cases:
            raise ValueError("FAP-Eval requires at least one case")
        if any(not str(case.case_id).strip() for case in self.cases):
            raise ValueError("FAP-Eval case_id is required")
        if len(ids) != len(set(ids)):
            raise ValueError("FAP-Eval case_id must be unique")
        if any(not str(case.ability).strip() for case in self.cases):
            raise ValueError("FAP-Eval ability is required")

    def run(self, solver: Callable[[EvalCase], Any]) -> EvalResult:
        if not callable(solver):
            raise TypeError("FAP-Eval solver must be callable")
        by: dict[str, dict[str, int]] = {}
        failures: list[dict[str, Any]] = []
        passed = 0
        for case in self.cases:
            row = by.setdefault(case.ability, {"total": 0, "passed": 0})
            row["total"] += 1
            try:
                actual = solver(case)
                ok = bool(case.evaluator(actual, case.expected))
                error = ""
            except Exception as exc:
                actual = None
                ok = False
                error = f"{type(exc).__name__}:{exc}"
            if ok:
                passed += 1
                row["passed"] += 1
            else:
                failures.append(
                    {
                        "case_id": case.case_id,
                        "ability": case.ability,
                        "payload": case.payload,
                        "expected": case.expected,
                        "actual": actual,
                        "error": error,
                    }
                )
        by_ability: dict[str, dict[str, Any]] = {}
        for ability, row in sorted(by.items()):
            total = row["total"]
            ok = row["passed"]
            by_ability[ability] = {
                "total": total,
                "passed": ok,
                "failed": total - ok,
                "accuracy": ok / total if total else 0.0,
            }
        total = len(self.cases)
        return EvalResult(
            total,
            passed,
            total - passed,
            passed / total if total else 0.0,
            by_ability,
            tuple(failures),
        )

    @staticmethod
    def failure_clusters(result: EvalResult) -> dict[str, tuple[Mapping[str, Any], ...]]:
        clusters: dict[str, list[Mapping[str, Any]]] = {}
        for failure in result.failures:
            clusters.setdefault(str(failure["ability"]), []).append(failure)
        return {
            ability: tuple(rows)
            for ability, rows in sorted(clusters.items())
        }


@dataclass(frozen=True)
class EvolvedSkill:
    parent_skill_id: str
    candidate: SkillSpec
    mutation: str


class SkillEvolution:
    """Mutate only declarative V86 binding DAGs; never generate source code."""

    def __init__(self, factory: GenericSkillFactory):
        self.factory = factory

    def mutate(
        self,
        parent: SkillSpec,
        *,
        max_variants: int = 8,
    ) -> list[EvolvedSkill]:
        variants: list[EvolvedSkill] = []
        seen: set[str] = {parent.skill_id}
        used = {node.binding_id for node in parent.nodes}
        bindings = self.factory.bindings.bindings

        for index, node in enumerate(parent.nodes):
            original = bindings.get(node.binding_id)
            if original is None:
                continue
            original_tags = {str(tag).strip().lower() for tag in original.tags}
            alternatives = []
            for binding in bindings.values():
                if (
                    binding.binding_id == node.binding_id
                    or binding.binding_id in used
                    or not self.factory.bindings.is_eligible(binding.binding_id)
                ):
                    continue
                tags = {str(tag).strip().lower() for tag in binding.tags}
                overlap = len(original_tags & tags)
                if overlap:
                    alternatives.append((-overlap, binding.binding_id, binding))
            alternatives.sort()
            for _, _, binding in alternatives:
                nodes = list(parent.nodes)
                nodes[index] = SkillNode(node.node_id, binding.binding_id)
                try:
                    candidate = SkillSpec.create(
                        name=f"{parent.name}_evo_replace_{index}",
                        ability=parent.ability,
                        tags=parent.tags,
                        nodes=tuple(nodes),
                        edges=parent.edges,
                        output_node=parent.output_node,
                    )
                except ValueError:
                    continue
                if candidate.skill_id not in seen:
                    seen.add(candidate.skill_id)
                    variants.append(
                        EvolvedSkill(
                            parent.skill_id,
                            candidate,
                            f"replace:{index}:{binding.binding_id}",
                        )
                    )
                if len(variants) >= max(1, int(max_variants)):
                    return variants
        return variants


@dataclass(frozen=True)
class RepairProposal:
    ability: str
    name: str
    required_tags: tuple[str, ...]
    difficulty: float
    unit_cases: tuple[SkillTestCase, ...]
    shadow_cases: tuple[SkillTestCase, ...]
    parent_skill_id: str = ""


@dataclass(frozen=True)
class ImprovementCycleResult:
    before_accuracy: float
    trial_accuracy: float
    after_accuracy: float
    target_ability: str
    attempted_repairs: int
    promoted_skills: tuple[str, ...]
    adopted_skills: tuple[str, ...]
    quarantined_skills: tuple[str, ...]
    remaining_failures: int
    accepted: bool
    regressed: bool
    scorecard: Mapping[str, Mapping[str, Any]]


class AutonomousImprovementCore:
    """V90-derived bounded benchmark -> repair -> re-evaluate control loop.

    V84 remains the canonical AbilityMap. V86 remains the canonical Skill
    Inventor / verifier / Registry / Skill Graph. This layer only coordinates
    independent evaluation, failure targeting, optional declarative evolution,
    and post-change acceptance.
    """

    def __init__(
        self,
        *,
        ability_map: AbilityMap,
        factory: GenericSkillFactory,
        evaluator: FAPEval,
        adaptive_bridge: Any | None = None,
    ):
        self.ability_map = ability_map
        self.factory = factory
        self.evaluator = evaluator
        self.adaptive_bridge = adaptive_bridge
        self.evolution = SkillEvolution(factory)
        self.adopted_skill_ids: set[str] = set()
        self.quarantined_skill_ids: set[str] = set()

    def _skill_matches(self, skill_id: str, ability: str) -> bool:
        try:
            record = self.factory.registry.get(skill_id)
        except Exception:
            return False
        if record.get("stage") != "active":
            return False
        skill = record.get("skill", {})
        return str(skill.get("ability", "")) == str(ability)

    def _solve(
        self,
        case: EvalCase,
        fallback_solver: Callable[[EvalCase], Any],
        *,
        trial_skill_id: str = "",
    ) -> Any:
        candidates: list[str] = []
        if trial_skill_id and self._skill_matches(trial_skill_id, case.ability):
            candidates.append(trial_skill_id)
        candidates.extend(
            sorted(
                skill_id
                for skill_id in self.adopted_skill_ids
                if self._skill_matches(skill_id, case.ability)
                and skill_id != trial_skill_id
            )
        )
        for skill_id in candidates:
            execution = self.factory.graph.execute(skill_id, case.payload)
            if execution.ok and not execution.timed_out:
                return execution.output
        return fallback_solver(case)

    def _observe_eval(self, result: EvalResult, *, difficulty: float = 0.5) -> None:
        for ability, row in result.by_ability.items():
            accuracy = float(row["accuracy"])
            self.ability_map.update(
                ability,
                difficulty,
                VerificationResult(
                    passed=accuracy >= 1.0,
                    reward=accuracy,
                    reason=f"v87_fap_eval:{row['passed']}/{row['total']}",
                    independent=True,
                ),
            )

    def _target(self, result: EvalResult) -> tuple[str, tuple[Mapping[str, Any], ...]]:
        clusters = self.evaluator.failure_clusters(result)
        if not clusters:
            return "", ()
        snapshot = self.ability_map.snapshot()
        target = max(
            clusters,
            key=lambda ability: (
                len(clusters[ability]),
                float(snapshot.get(ability, {}).get("weakness", 0.0)),
                ability,
            ),
        )
        return target, clusters[target]

    def _promote_proposal(
        self,
        proposal: RepairProposal,
        *,
        max_repairs: int,
    ) -> tuple[str, int]:
        attempts = 0
        if proposal.parent_skill_id:
            try:
                parent_record = self.factory.registry.get(proposal.parent_skill_id)
                parent = SkillSpec.from_dict(parent_record["skill"])
            except Exception:
                return "", attempts
            for evolved in self.evolution.mutate(
                parent,
                max_variants=max_repairs,
            ):
                attempts += 1
                decision = self.factory.promotion.evaluate(
                    evolved.candidate,
                    unit_cases=proposal.unit_cases,
                    shadow_cases=proposal.shadow_cases,
                )
                if decision.promoted and decision.stage == "active":
                    return evolved.candidate.skill_id, attempts
            return "", attempts

        attempts = 1
        try:
            spec, decision = self.factory.invent_and_promote(
                name=proposal.name,
                ability=proposal.ability,
                required_tags=proposal.required_tags,
                unit_cases=proposal.unit_cases,
                shadow_cases=proposal.shadow_cases,
            )
        except Exception:
            return "", attempts
        if decision.promoted and decision.stage == "active":
            return spec.skill_id, attempts
        return "", attempts

    def cycle(
        self,
        *,
        fallback_solver: Callable[[EvalCase], Any],
        proposal_provider: Callable[
            [str, Sequence[Mapping[str, Any]]],
            Optional[RepairProposal],
        ],
        max_repairs: int = 3,
    ) -> ImprovementCycleResult:
        if max_repairs < 1:
            raise ValueError("max_repairs must be positive")
        baseline = self.evaluator.run(
            lambda case: self._solve(case, fallback_solver)
        )
        self._observe_eval(baseline)
        target, failures = self._target(baseline)

        promoted: list[str] = []
        adopted: list[str] = []
        quarantined: list[str] = []
        attempts = 0
        trial = baseline
        settled = baseline
        accepted = False
        regressed = False

        if target:
            proposal = proposal_provider(target, failures)
            if proposal is not None:
                if proposal.ability != target:
                    raise ValueError("repair proposal ability must match target")
                trial_skill_id, attempts = self._promote_proposal(
                    proposal,
                    max_repairs=max_repairs,
                )
                if trial_skill_id:
                    promoted.append(trial_skill_id)
                    trial = self.evaluator.run(
                        lambda case: self._solve(
                            case,
                            fallback_solver,
                            trial_skill_id=trial_skill_id,
                        )
                    )
                    before_target = float(
                        baseline.by_ability.get(target, {}).get("accuracy", 0.0)
                    )
                    trial_target = float(
                        trial.by_ability.get(target, {}).get("accuracy", 0.0)
                    )
                    regressed = trial.accuracy + 1e-12 < baseline.accuracy
                    accepted = (
                        not regressed
                        and trial_target > before_target + 1e-12
                    )
                    if accepted:
                        self.adopted_skill_ids.add(trial_skill_id)
                        self.quarantined_skill_ids.discard(trial_skill_id)
                        adopted.append(trial_skill_id)
                        settled = trial
                        if self.adaptive_bridge is not None:
                            self.adaptive_bridge.sync_active()
                    else:
                        self.quarantined_skill_ids.add(trial_skill_id)
                        quarantined.append(trial_skill_id)
                        settled = self.evaluator.run(
                            lambda case: self._solve(case, fallback_solver)
                        )

        self._observe_eval(settled)
        return ImprovementCycleResult(
            before_accuracy=baseline.accuracy,
            trial_accuracy=trial.accuracy,
            after_accuracy=settled.accuracy,
            target_ability=target,
            attempted_repairs=attempts,
            promoted_skills=tuple(promoted),
            adopted_skills=tuple(adopted),
            quarantined_skills=tuple(quarantined),
            remaining_failures=settled.failed,
            accepted=accepted,
            regressed=regressed,
            scorecard=self.ability_map.snapshot(),
        )
