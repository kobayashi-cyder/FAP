from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from fap_generic_skill import SkillSpec, SkillTestCase
from fap_self_curriculum import (
    AttemptResult,
    CurriculumGenerator,
    PatternStore,
    SuccessCompressor,
    VerificationResult,
)

from .core import AutonomousImprovementCore, EvalCase, EvalResult, RepairProposal


_REQUIRED_EVIDENCE_KEYS = (
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
)


def _jsonable(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )


@dataclass(frozen=True)
class RepairRecipe:
    """Pre-registered repair recipe; selection is automatic inside a cycle."""

    ability: str
    name: str
    required_tags: tuple[str, ...]
    unit_cases: tuple[SkillTestCase, ...]
    shadow_cases: tuple[SkillTestCase, ...]
    parent_skill_id: str = ""

    def proposal(self, difficulty: float) -> RepairProposal:
        return RepairProposal(
            ability=self.ability,
            name=self.name,
            required_tags=self.required_tags,
            difficulty=float(difficulty),
            unit_cases=self.unit_cases,
            shadow_cases=self.shadow_cases,
            parent_skill_id=self.parent_skill_id,
        )


@dataclass(frozen=True)
class UnifiedCycleResult:
    evidence_id: str
    accepted: bool
    selected_weakness: str
    before_accuracy: float
    trial_accuracy: float
    after_accuracy: float
    candidate_skill_id: str
    routed_skill_ids: tuple[str, ...]
    memory_persisted: bool


class CycleEvidenceStore:
    """Append-only, restart-safe evidence for both accepted and rejected cycles."""

    SCHEMA = "fap.self-improvement-evidence.v1"

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self.records: list[dict[str, Any]] = []
        if self.path and self.path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("self-improvement evidence store is unreadable") from exc
        if payload.get("schema") != self.SCHEMA:
            raise ValueError("unsupported self-improvement evidence schema")
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError("self-improvement evidence records missing")
        seen: set[str] = set()
        validated: list[dict[str, Any]] = []
        for raw in records:
            if not isinstance(raw, dict):
                raise ValueError("invalid self-improvement evidence record")
            evidence_id = str(raw.get("evidence_id", "")).strip()
            if not evidence_id or evidence_id in seen:
                raise ValueError("invalid or duplicate self-improvement evidence id")
            if any(key not in raw for key in _REQUIRED_EVIDENCE_KEYS):
                raise ValueError("self-improvement evidence record is incomplete")
            seen.add(evidence_id)
            validated.append(raw)
        self.records = validated

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                {"schema": self.SCHEMA, "records": self.records},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _jsonable(dict(record))
        missing = [key for key in _REQUIRED_EVIDENCE_KEYS if key not in normalized]
        if missing:
            raise ValueError(
                "missing self-improvement evidence: " + ", ".join(sorted(missing))
            )
        canonical = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_id = sha256(canonical.encode("utf-8")).hexdigest()
        existing = next(
            (row for row in self.records if row["evidence_id"] == evidence_id),
            None,
        )
        if existing is not None:
            return existing
        row = {"evidence_id": evidence_id, **normalized}
        self.records.append(row)
        self._save()
        return row

    def adopted_skill_ids(self) -> set[str]:
        out: set[str] = set()
        for row in self.records:
            decision = row.get("promotion_or_rejection_decision", {})
            if decision.get("action") == "PROMOTED":
                skill_id = str(decision.get("skill_id", "")).strip()
                if skill_id:
                    out.add(skill_id)
        return out

    def quarantined_skill_ids(self) -> set[str]:
        out: set[str] = set()
        for row in self.records:
            decision = row.get("promotion_or_rejection_decision", {})
            if decision.get("action") == "REJECTED":
                skill_id = str(decision.get("skill_id", "")).strip()
                if skill_id:
                    out.add(skill_id)
        return out


class UnifiedSelfImprovementLoop:
    """Close the V84/V82/V86/V87 self-improvement graph without manual node choice."""

    def __init__(
        self,
        *,
        core: AutonomousImprovementCore,
        fallback_solver: Callable[[EvalCase], Any],
        repair_recipes: Mapping[str, RepairRecipe],
        evidence_store: Optional[CycleEvidenceStore] = None,
        pattern_store: Optional[PatternStore] = None,
        curriculum_generator: Optional[CurriculumGenerator] = None,
        success_compressor: Optional[SuccessCompressor] = None,
    ):
        if not callable(fallback_solver):
            raise TypeError("fallback_solver must be callable")
        if core.adaptive_bridge is None:
            raise ValueError("unified self-improvement loop requires sparse routing bridge")
        self.core = core
        self.fallback_solver = fallback_solver
        self.repair_recipes = {
            str(key): value for key, value in repair_recipes.items()
        }
        self.evidence_store = evidence_store or CycleEvidenceStore()
        self.pattern_store = pattern_store or PatternStore()
        self.curriculum_generator = curriculum_generator or CurriculumGenerator()
        self.success_compressor = success_compressor or SuccessCompressor()

        # Reconstruct V87 final-adoption state from append-only evidence.
        self.core.adopted_skill_ids.update(self.evidence_store.adopted_skill_ids())
        self.core.quarantined_skill_ids.update(
            self.evidence_store.quarantined_skill_ids()
        )

    def _assess(self) -> tuple[EvalResult, str, tuple[Mapping[str, Any], ...]]:
        baseline = self.core.evaluator.run(
            lambda case: self.core._solve(case, self.fallback_solver)
        )
        self.core._observe_eval(baseline)
        target, failures = self.core._target(baseline)
        return baseline, target, failures

    def _candidate(
        self,
        proposal: RepairProposal,
        *,
        max_repairs: int,
    ) -> tuple[
        Optional[SkillSpec],
        Any,
        int,
        tuple[Mapping[str, Any], ...],
        str,
    ]:
        attempts = 0
        records: list[Mapping[str, Any]] = []
        factory = self.core.factory
        try:
            if proposal.parent_skill_id:
                parent_record = factory.registry.get(proposal.parent_skill_id)
                parent = SkillSpec.from_dict(parent_record["skill"])
                variants = self.core.evolution.mutate(
                    parent,
                    max_variants=max_repairs,
                )
                selected_spec: Optional[SkillSpec] = None
                selected_decision = None
                for evolved in variants:
                    attempts += 1
                    decision = factory.promotion.evaluate(
                        evolved.candidate,
                        unit_cases=proposal.unit_cases,
                        shadow_cases=proposal.shadow_cases,
                    )
                    records.append(
                        {
                            "skill_id": evolved.candidate.skill_id,
                            "mutation": evolved.mutation,
                            "decision": asdict(decision),
                        }
                    )
                    selected_spec = evolved.candidate
                    selected_decision = decision
                    if decision.promoted and decision.stage == "active":
                        break
                return (
                    selected_spec,
                    selected_decision,
                    attempts,
                    tuple(records),
                    "",
                )

            attempts = 1
            spec = factory.inventor.invent(
                name=proposal.name,
                ability=proposal.ability,
                required_tags=proposal.required_tags,
            )
            decision = factory.promotion.evaluate(
                spec,
                unit_cases=proposal.unit_cases,
                shadow_cases=proposal.shadow_cases,
            )
            records.append(
                {
                    "skill_id": spec.skill_id,
                    "mutation": "invent",
                    "decision": asdict(decision),
                }
            )
            return spec, decision, attempts, tuple(records), ""
        except Exception as exc:
            return (
                None,
                None,
                attempts,
                tuple(records),
                f"{type(exc).__name__}:{exc}",
            )

    @staticmethod
    def _score(result: EvalResult, ability: str) -> float:
        return float(result.by_ability.get(ability, {}).get("accuracy", 0.0))

    def _route_and_remember(
        self,
        *,
        task_text: str,
        payload: Any,
        evidence_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        bridge = self.core.adaptive_bridge
        allowed = set(self.core.adopted_skill_ids)
        decision, executions = bridge.execute(
            task_text,
            payload,
            allowed_skill_ids=allowed,
        )
        observed = False
        if decision.selected:
            observed = bridge.observe(
                decision,
                executions,
                evidence_id=evidence_token,
            )
        trace = {
            "task": decision.task,
            "allowed_skill_ids": sorted(allowed),
            "selected": [
                {
                    "circuit_id": choice.circuit_id,
                    "score": choice.score,
                    "similarity": choice.similarity,
                    "memory_boost": choice.memory_boost,
                }
                for choice in decision.selected
            ],
            "executions": [
                {
                    "skill_id": row.skill_id,
                    "ok": row.execution.ok,
                    "timed_out": row.execution.timed_out,
                    "steps": row.execution.steps,
                    "error": row.execution.error,
                }
                for row in executions
            ],
            "verified_runtime_observation": observed,
        }
        active_rows = {}
        for skill_id in decision.circuit_ids:
            entry = bridge.controller.memory.entries.get(skill_id)
            if entry is not None:
                active_rows[skill_id] = asdict(entry)
        return trace, {"active_memory": active_rows}

    def run(
        self,
        *,
        input_state: Any = None,
        max_repairs: int = 3,
    ) -> UnifiedCycleResult:
        if max_repairs < 1:
            raise ValueError("max_repairs must be positive")

        capability_before = self.core.ability_map.snapshot()
        baseline, target, failures = self._assess()

        if not target:
            record = self.evidence_store.append(
                {
                    "input_state": _jsonable(input_state),
                    "capability_map_before": capability_before,
                    "selected_weakness": "",
                    "generated_task": {},
                    "router_trace": {
                        "task": "",
                        "allowed_skill_ids": sorted(self.core.adopted_skill_ids),
                        "selected": [],
                        "executions": [],
                        "verified_runtime_observation": False,
                    },
                    "candidate_skill": {},
                    "sandbox_result": {"attempts": 0, "records": []},
                    "verifier_result": {
                        "passed": True,
                        "reason": "no_measurable_failure_cluster",
                    },
                    "promotion_or_rejection_decision": {
                        "action": "NOOP",
                        "skill_id": "",
                        "reason": "capability_already_passes_current_eval",
                    },
                    "memory_record": {},
                    "capability_map_after": self.core.ability_map.snapshot(),
                    "evaluation": {
                        "before_accuracy": baseline.accuracy,
                        "trial_accuracy": baseline.accuracy,
                        "after_accuracy": baseline.accuracy,
                    },
                }
            )
            return UnifiedCycleResult(
                record["evidence_id"],
                False,
                "",
                baseline.accuracy,
                baseline.accuracy,
                baseline.accuracy,
                "",
                (),
                False,
            )

        state = self.core.ability_map.states[target]
        priors = self.pattern_store.for_ability(target)
        task = self.curriculum_generator.generate(state, priors)
        recipe = self.repair_recipes.get(target)

        trial = baseline
        settled = baseline
        candidate: Optional[SkillSpec] = None
        decision = None
        attempts = 0
        candidate_records: tuple[Mapping[str, Any], ...] = ()
        candidate_error = ""
        accepted = False
        regressed = False
        final_reason = "no_registered_repair_recipe"

        if recipe is not None:
            proposal = recipe.proposal(task.difficulty)
            (
                candidate,
                decision,
                attempts,
                candidate_records,
                candidate_error,
            ) = self._candidate(proposal, max_repairs=max_repairs)
            if (
                candidate is not None
                and decision is not None
                and decision.promoted
                and decision.stage == "active"
            ):
                trial = self.core.evaluator.run(
                    lambda case: self.core._solve(
                        case,
                        self.fallback_solver,
                        trial_skill_id=candidate.skill_id,
                    )
                )
                before_target = self._score(baseline, target)
                trial_target = self._score(trial, target)
                regressed = trial.accuracy + 1e-12 < baseline.accuracy
                accepted = (
                    not regressed
                    and trial_target > before_target + 1e-12
                )
                if accepted:
                    self.core.adopted_skill_ids.add(candidate.skill_id)
                    self.core.quarantined_skill_ids.discard(candidate.skill_id)
                    settled = trial
                    final_reason = "target_improved_without_global_regression"
                else:
                    self.core.quarantined_skill_ids.add(candidate.skill_id)
                    settled = self.core.evaluator.run(
                        lambda case: self.core._solve(
                            case,
                            self.fallback_solver,
                        )
                    )
                    final_reason = (
                        "global_regression"
                        if regressed
                        else "no_measurable_target_improvement"
                    )
            elif candidate_error:
                final_reason = candidate_error
            elif decision is not None:
                final_reason = str(decision.reason)
            else:
                final_reason = "no_candidate_generated"

        self.core._observe_eval(settled)
        capability_after = self.core.ability_map.snapshot()

        skill_id = candidate.skill_id if candidate is not None else ""
        cycle_seed = {
            "input_state": _jsonable(input_state),
            "selected_weakness": target,
            "task": asdict(task),
            "candidate_skill_id": skill_id,
            "before_accuracy": baseline.accuracy,
            "trial_accuracy": trial.accuracy,
            "after_accuracy": settled.accuracy,
            "accepted": accepted,
        }
        evidence_token = sha256(
            json.dumps(
                cycle_seed,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:24]

        representative_payload = (
            failures[0].get("payload")
            if failures
            else None
        )
        route_query = " ".join(
            [
                task.prompt,
                target,
                *(recipe.required_tags if recipe is not None else ()),
            ]
        )
        router_trace: dict[str, Any] = {
            "task": route_query,
            "allowed_skill_ids": sorted(self.core.adopted_skill_ids),
            "selected": [],
            "executions": [],
            "verified_runtime_observation": False,
        }
        runtime_memory: dict[str, Any] = {"active_memory": {}}
        if accepted:
            router_trace, runtime_memory = self._route_and_remember(
                task_text=route_query,
                payload=representative_payload,
                evidence_token=evidence_token,
            )

        pattern_record: dict[str, Any] = {}
        if accepted and candidate is not None:
            verifier_payload = asdict(decision)
            verification = VerificationResult(
                passed=True,
                reward=self._score(settled, target),
                reason="unified_self_improvement_loop:accepted",
                independent=True,
            )
            attempt = AttemptResult(
                answer=f"adopted_skill:{candidate.skill_id}",
                evidence={
                    "cycle_token": evidence_token,
                    "skill_id": candidate.skill_id,
                    "verifier": verifier_payload,
                    "router": router_trace,
                },
            )
            pattern = self.success_compressor.compress(
                task,
                attempt,
                verification,
            )
            stored = self.pattern_store.add(pattern)
            pattern_record = {
                "pattern_id": pattern.pattern_id,
                "stored": stored,
                "stage": (
                    self.pattern_store.patterns[pattern.pattern_id].stage
                    if pattern.pattern_id in self.pattern_store.patterns
                    else pattern.stage
                ),
                "evidence_digests": list(pattern.evidence_digests),
            }

        registry_evidence: Mapping[str, Any] = {}
        if candidate is not None:
            try:
                registry_evidence = dict(
                    self.core.factory.registry.get(candidate.skill_id).get(
                        "evidence",
                        {},
                    )
                )
            except Exception:
                registry_evidence = {}

        action = (
            "PROMOTED"
            if accepted
            else "REJECTED"
            if candidate is not None or recipe is not None
            else "NOOP"
        )
        verifier_result = (
            asdict(decision)
            if decision is not None
            else {
                "passed": False,
                "reason": final_reason,
            }
        )
        memory_record = {
            **runtime_memory,
            "compressed_success": pattern_record,
            "evidence_token": evidence_token,
        }

        record = self.evidence_store.append(
            {
                "input_state": _jsonable(input_state),
                "capability_map_before": capability_before,
                "selected_weakness": target,
                "generated_task": asdict(task),
                "router_trace": router_trace,
                "candidate_skill": (
                    candidate.to_dict()
                    if candidate is not None
                    else {"error": candidate_error or final_reason}
                ),
                "sandbox_result": {
                    "attempts": attempts,
                    "records": list(candidate_records),
                    "registry_evidence": registry_evidence,
                },
                "verifier_result": verifier_result,
                "promotion_or_rejection_decision": {
                    "action": action,
                    "skill_id": skill_id,
                    "accepted": accepted,
                    "regressed": regressed,
                    "reason": final_reason,
                },
                "memory_record": memory_record,
                "capability_map_after": capability_after,
                "evaluation": {
                    "before_accuracy": baseline.accuracy,
                    "trial_accuracy": trial.accuracy,
                    "after_accuracy": settled.accuracy,
                    "target_before": self._score(baseline, target),
                    "target_trial": self._score(trial, target),
                    "target_after": self._score(settled, target),
                    "remaining_failures": settled.failed,
                },
            }
        )

        routed_skill_ids = tuple(
            str(row["circuit_id"])
            for row in router_trace.get("selected", [])
        )
        memory_persisted = bool(
            pattern_record.get("stored")
            or runtime_memory.get("active_memory")
        )
        return UnifiedCycleResult(
            evidence_id=record["evidence_id"],
            accepted=accepted,
            selected_weakness=target,
            before_accuracy=baseline.accuracy,
            trial_accuracy=trial.accuracy,
            after_accuracy=settled.accuracy,
            candidate_skill_id=skill_id,
            routed_skill_ids=routed_skill_ids,
            memory_persisted=memory_persisted,
        )
