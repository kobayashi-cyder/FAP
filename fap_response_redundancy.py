from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, isfinite
import re


def _clip(value: object, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(x):
        return default
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class ResponseLane:
    lane_id: str
    role: str
    group: str
    variant: int
    priority: float
    verifier: bool
    partial_ok: bool = True


@dataclass(frozen=True)
class ResponseSeriesPlan:
    contract: str
    capacity: int
    active_lanes: int
    synthesis_width: int
    quorum: int
    independent_groups: int
    pressure: float
    coverage_target: float
    partial_coverage_allowed: bool
    lanes: tuple[ResponseLane, ...]

    def to_dict(self, *, include_lanes: bool = True) -> dict:
        out = {
            "contract": self.contract,
            "capacity": self.capacity,
            "active_lanes": self.active_lanes,
            "synthesis_width": self.synthesis_width,
            "quorum": self.quorum,
            "independent_groups": self.independent_groups,
            "pressure": round(self.pressure, 4),
            "coverage_target": round(self.coverage_target, 4),
            "partial_coverage_allowed": self.partial_coverage_allowed,
        }
        if include_lanes:
            out["lanes"] = [asdict(x) for x in self.lanes]
        return out


class ResponseRedundancyPlanner:
    """Domain-neutral response-series expansion.

    It increases independent response/evaluation lanes under uncertainty,
    breadth, disagreement and verification pressure. It intentionally does not
    require exhaustive coverage: the target remains below 1.0 so the runtime
    can answer the most salient parts instead of padding every possible facet.
    """

    CONTRACT = "fap.response.series.v1"
    MAX_LANES = 128
    MAX_SYNTHESIS = 16

    ROLES = (
        ("direct", "answer"),
        ("decomposition", "structure"),
        ("assumptions", "structure"),
        ("mechanism", "explanation"),
        ("evidence", "grounding"),
        ("counterexample", "challenge"),
        ("constraints", "requirements"),
        ("edge_cases", "challenge"),
        ("alternatives", "diversity"),
        ("procedure", "action"),
        ("analogy", "explanation"),
        ("uncertainty", "grounding"),
        ("user_intent", "requirements"),
        ("compression", "synthesis"),
        ("verifier", "verification"),
        ("synthesis_probe", "synthesis"),
    )

    @staticmethod
    def structural_pressure(text: str, intent_count: int = 0) -> float:
        value = str(text or "")
        chars = min(1.0, len(value) / 1600.0)
        separators = sum(value.count(x) for x in ("\n", "。", "！", "？", ";", "；", ":", "："))
        sep_score = min(1.0, separators / 24.0)
        chunks = [x for x in re.split(r"[\n。！？!?;；]+", value) if x.strip()]
        chunk_score = min(1.0, max(0, len(chunks) - 1) / 12.0)
        intent_score = min(1.0, max(0, int(intent_count) - 1) / 6.0)
        return _clip(0.40 * chars + 0.25 * sep_score + 0.20 * chunk_score + 0.15 * intent_score)

    def plan(
        self,
        text: str,
        *,
        uncertainty: float = 0.0,
        confidence: float = 1.0,
        disagreement: bool = False,
        counterexample: bool = False,
        route_candidates: int = 1,
        verification_depth: int = 1,
        retries: int = 0,
        intent_count: int = 0,
        has_route: bool = False,
    ) -> ResponseSeriesPlan:
        route_candidates = max(1, min(8, int(route_candidates or 1)))
        verification_depth = max(1, min(6, int(verification_depth or 1)))
        retries = max(0, min(4, int(retries or 0)))
        intent_count = max(0, min(16, int(intent_count or 0)))

        structural = self.structural_pressure(text, intent_count)
        pressure = _clip(
            0.18 * _clip(uncertainty)
            + 0.18 * (1.0 - _clip(confidence, 1.0))
            + 0.10 * int(bool(disagreement))
            + 0.10 * int(bool(counterexample))
            + 0.16 * structural
            + 0.10 * ((route_candidates - 1) / 7.0)
            + 0.10 * ((verification_depth - 1) / 5.0)
            + 0.08 * (retries / 4.0)
        )
        if not has_route and str(text or "").strip():
            pressure = min(1.0, pressure + 0.04)

        active = round(
            6
            + 118 * pressure
            + 2 * retries
            + 2 * max(0, intent_count - 1)
        )
        active = max(6, min(self.MAX_LANES, active))
        synthesis_width = max(2, min(self.MAX_SYNTHESIS, 2 + active // 8))
        quorum = max(2, min(synthesis_width, ceil(synthesis_width * 2 / 3)))
        independent_groups = max(4, min(len(self.ROLES), (active + 2) // 3))
        coverage_target = min(0.90, 0.55 + 0.35 * pressure)

        lanes: list[ResponseLane] = []
        for i in range(active):
            role, group = self.ROLES[i % len(self.ROLES)]
            variant = i // len(self.ROLES)
            verifier = role in {"evidence", "counterexample", "uncertainty", "verifier", "synthesis_probe"}
            priority = max(0.35, 1.0 - (i / max(1, active * 2.4)))
            lanes.append(
                ResponseLane(
                    lane_id=f"{group}:{role}:{variant}",
                    role=role,
                    group=group,
                    variant=variant,
                    priority=round(priority, 4),
                    verifier=verifier,
                )
            )

        return ResponseSeriesPlan(
            contract=self.CONTRACT,
            capacity=self.MAX_LANES,
            active_lanes=active,
            synthesis_width=synthesis_width,
            quorum=quorum,
            independent_groups=independent_groups,
            pressure=pressure,
            coverage_target=coverage_target,
            partial_coverage_allowed=True,
            lanes=tuple(lanes),
        )
