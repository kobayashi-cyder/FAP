from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from fap_generic_skill import GenericSkillFactory, SkillBuildRequest, SkillSpec
from fap_self_curriculum import AbilityMap, VerificationResult

from .deployment import VerifiedSkillDeployment
from .eval import EvalCase, EvalObservation, EvalResult, FAPEval


class CycleLedger:
    """Replay-protect autonomous improvement cycles across restart."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self.seen: set[str] = set()
        if self.path and self.path.is_file():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("V90 cycle ledger is unreadable") from exc
            if (
                not isinstance(payload, dict)
                or set(payload) != {"schema", "cycle_ids"}
                or payload["schema"] != "fap.autonomous-improvement-ledger.v1"
                or not isinstance(payload["cycle_ids"], list)
                or any(not isinstance(x, str) or not x.strip() for x in payload["cycle_ids"])
                or len(payload["cycle_ids"]) != len(set(payload["cycle_ids"]))
            ):
                raise ValueError("invalid V90 cycle ledger")
            self.seen.update(payload["cycle_ids"])

    def reserve(self, cycle_id: str) -> None:
        cycle_id = str(cycle_id).strip()
        if not cycle_id:
            raise ValueError("V90 cycle_id is required")
        if cycle_id in self.seen:
            raise ValueError("duplicate V90 improvement cycle")
        self.seen.add(cycle_id)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "schema": "fap.autonomous-improvement-ledger.v1",
                        "cycle_ids": sorted(self.seen),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            tmp.replace(self.path)


@dataclass(frozen=True)
class ImprovementCycleResult:
    cycle_id: str
    before_accuracy: float
    after_accuracy: float
    target_ability: str
    attempted_repairs: int
    locally_promoted_skills: tuple[str, ...]
    deployed_skills: tuple[str, ...]
    rolled_back_skills: tuple[str, ...]
    remaining_failures: int
    globally_accepted: bool
    reason: str
    scorecard: dict[str, dict[str, Any]]


class AutonomousImprovementCore:
    """Benchmark -> failure cluster -> V86 Skill Factory -> global eval -> deploy/rollback."""

    def __init__(
        self,
        *,
        ability_map: AbilityMap,
        factory: GenericSkillFactory,
        evaluator: FAPEval,
        deployment: VerifiedSkillDeployment | None = None,
        ledger_path: Optional[str | Path] = None,
    ):
        self.ability_map = ability_map
        self.factory = factory
        self.evaluator = evaluator
        self.deployment = deployment or VerifiedSkillDeployment(factory)
        self.ledger = CycleLedger(ledger_path)

    def _fallback_adapter(
        self,
        case: EvalCase,
        fallback_solver: Callable[[EvalCase], Any],
        *,
        include_staged: bool,
    ) -> Any:
        return self.deployment.solve(
            case.ability,
            case.payload,
            lambda _payload: fallback_solver(case),
            include_staged=include_staged,
        )

    def _select_target(self, baseline: EvalResult) -> tuple[str, list[EvalObservation]]:
        clusters = self.evaluator.failure_clusters(baseline)
        if not clusters:
            return "", []
        snapshot = self.ability_map.snapshot()
        target = max(
            clusters,
            key=lambda ability: (
                len(clusters[ability]),
                snapshot.get(ability, {}).get("weakness", 0.5),
                ability,
            ),
        )
        return target, clusters[target]

    @staticmethod
    def _no_regressions(before: EvalResult, trial: EvalResult) -> bool:
        abilities = set(before.by_ability) | set(trial.by_ability)
        for ability in abilities:
            before_acc = float(before.by_ability.get(ability, {}).get("accuracy", 0.0))
            trial_acc = float(trial.by_ability.get(ability, {}).get("accuracy", 0.0))
            if trial_acc + 1e-12 < before_acc:
                return False
        return True

    @staticmethod
    def _target_improved(before: EvalResult, trial: EvalResult, target: str) -> bool:
        return (
            float(trial.by_ability.get(target, {}).get("accuracy", 0.0))
            > float(before.by_ability.get(target, {}).get("accuracy", 0.0)) + 1e-12
        )

    def _update_ability_map(self, result: EvalResult, *, cycle_id: str) -> None:
        for row in result.observations:
            self.ability_map.update(
                row.ability,
                row.difficulty,
                VerificationResult(
                    row.passed,
                    1.0 if row.passed else 0.0,
                    f"v90_eval:{cycle_id}:{row.case_id}",
                    independent=True,
                ),
            )

    def cycle(
        self,
        *,
        cycle_id: str,
        fallback_solver: Callable[[EvalCase], Any],
        proposal_provider: Callable[
            [str, Sequence[EvalObservation], int],
            SkillBuildRequest | None,
        ],
        max_repairs: int = 3,
    ) -> ImprovementCycleResult:
        if not callable(fallback_solver) or not callable(proposal_provider):
            raise TypeError("V90 fallback_solver and proposal_provider must be callable")
        self.ledger.reserve(cycle_id)

        baseline = self.evaluator.run(
            lambda case: self._fallback_adapter(
                case,
                fallback_solver,
                include_staged=False,
            )
        )
        target, failures = self._select_target(baseline)
        locally_promoted: list[str] = []
        deployed: list[str] = []
        rolled_back: list[str] = []
        attempts = 0
        accepted = False
        reason = "no_failures" if not target else "no_verified_repair"
        trial: EvalResult | None = None

        if target:
            for attempt_index in range(1, max(0, int(max_repairs)) + 1):
                attempts += 1
                request = proposal_provider(target, failures, attempt_index)
                if request is None:
                    reason = "proposal_provider_exhausted"
                    break
                if request.ability != target:
                    reason = "proposal_ability_mismatch"
                    continue

                spec, decision = self.factory.invent_and_promote(
                    name=request.name,
                    ability=request.ability,
                    required_tags=request.required_tags,
                    unit_cases=request.unit_cases,
                    shadow_cases=request.shadow_cases,
                )
                if not decision.promoted or decision.stage != "active":
                    reason = f"local_verification_failed:{decision.reason}"
                    continue

                locally_promoted.append(spec.skill_id)
                try:
                    self.deployment.stage(
                        spec.skill_id,
                        evidence_id=f"{cycle_id}:{attempt_index}",
                    )
                except Exception as exc:
                    reason = f"deployment_stage_failed:{type(exc).__name__}"
                    continue

                trial = self.evaluator.run(
                    lambda case: self._fallback_adapter(
                        case,
                        fallback_solver,
                        include_staged=True,
                    )
                )
                if (
                    trial.accuracy + 1e-12 >= baseline.accuracy
                    and self._no_regressions(baseline, trial)
                    and self._target_improved(baseline, trial, target)
                ):
                    self.deployment.accept(spec.skill_id)
                    deployed.append(spec.skill_id)
                    accepted = True
                    reason = "global_eval_accepted"
                    break

                self.deployment.reject(spec.skill_id)
                rolled_back.append(spec.skill_id)
                reason = "global_eval_rejected"

        if accepted:
            after = self.evaluator.run(
                lambda case: self._fallback_adapter(
                    case,
                    fallback_solver,
                    include_staged=False,
                )
            )
            if (
                after.accuracy + 1e-12 < baseline.accuracy
                or not self._no_regressions(baseline, after)
                or not self._target_improved(baseline, after, target)
            ):
                for skill_id in tuple(deployed):
                    self.deployment.reject(skill_id)
                    rolled_back.append(skill_id)
                deployed.clear()
                accepted = False
                reason = "post_deploy_regression_rolled_back"
                after = baseline
        else:
            after = baseline

        self._update_ability_map(after, cycle_id=cycle_id)

        return ImprovementCycleResult(
            cycle_id=str(cycle_id),
            before_accuracy=baseline.accuracy,
            after_accuracy=after.accuracy,
            target_ability=target,
            attempted_repairs=attempts,
            locally_promoted_skills=tuple(locally_promoted),
            deployed_skills=tuple(deployed),
            rolled_back_skills=tuple(rolled_back),
            remaining_failures=after.failed,
            globally_accepted=accepted,
            reason=reason,
            scorecard=self.ability_map.snapshot(),
        )
