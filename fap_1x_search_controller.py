from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from fap_1x_problem_decomposer import ProblemDecomposition


@dataclass(frozen=True)
class AdaptiveSearchPolicy:
    risk: float
    max_rounds: int
    branch_budget: int
    require_verified: bool
    repeat_independent_verification: bool
    allow_supported: bool
    allow_provisional: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptiveSearchController:
    """Convert generic risk/disagreement signals into bounded compute policy."""

    def policy(
        self,
        decomposition: ProblemDecomposition,
        *,
        disagreement: bool = False,
        candidate_verifications: Iterable[str] = (),
    ) -> AdaptiveSearchPolicy:
        risk = float(decomposition.risk)
        states = tuple(str(x) for x in candidate_verifications)
        reasons: list[str] = []

        if risk < 0.35:
            rounds = 1
            branches = 3
        elif risk < 0.65:
            rounds = 2
            branches = 6
            reasons.append("moderate_task_risk")
        else:
            rounds = 3
            branches = 10
            reasons.append("high_task_risk")

        if disagreement:
            rounds = max(rounds, 3)
            branches = max(branches, 10)
            reasons.append("candidate_disagreement")

        if "rejected" in states:
            rounds = max(rounds, 2)
            branches = max(branches, 6)
            reasons.append("verification_rejection")

        require_verified = bool(
            disagreement
            or risk >= 0.55
            or decomposition.task_kind in {"coding", "derivation"}
        )
        repeat = bool(disagreement or risk >= 0.45)
        allow_supported = not require_verified
        allow_provisional = decomposition.task_kind == "hypothesis"

        if require_verified:
            reasons.append("verified_result_required")
        if repeat:
            reasons.append("repeat_independent_verification")

        return AdaptiveSearchPolicy(
            risk=round(risk, 3),
            max_rounds=rounds,
            branch_budget=branches,
            require_verified=require_verified,
            repeat_independent_verification=repeat,
            allow_supported=allow_supported,
            allow_provisional=allow_provisional,
            reasons=tuple(dict.fromkeys(reasons)),
        )
