from __future__ import annotations

from dataclasses import asdict, dataclass

from fap_dynamic_sparse_routing import (
    DynamicSparseConfig,
    DynamicSparseRouter,
    RouteSpec,
    RoutingContext,
    RoutingFeedback,
)


@dataclass(frozen=True)
class SparseRoutingBenchmark:
    version: str
    passed: int
    total: int
    score: float
    initial_density: float
    trained_density: float
    high_risk_density: float
    specialist_hits: int
    specialist_total: int
    checks: tuple[tuple[str, bool], ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _routes() -> tuple[RouteSpec, ...]:
    return (
        RouteSpec("reader", ("retrieval", "evidence"), ("language", "social"), ("reading",), ("evidence_selection",), 0.60, 1.0),
        RouteSpec("symbolic", ("algebra", "logic"), ("math", "science"), ("symbolic", "multi_step"), ("logic", "decomposition"), 0.62, 1.1),
        RouteSpec("numeric", ("arithmetic", "numeric"), ("math", "science"), ("numeric", "multi_step"), ("arithmetic",), 0.61, 0.9),
        RouteSpec("verifier", ("verification", "counterexample"), ("math", "science", "language", "social"), ("reading", "symbolic", "numeric", "multi_step"), ("verification",), 0.58, 1.1),
        RouteSpec("decomposer", ("planning", "decomposition"), ("math", "science", "language"), ("multi_step",), ("decomposition",), 0.57, 1.0),
        RouteSpec("fallback", ("general",), ("math", "science", "language", "social"), ("reading", "symbolic", "numeric", "multi_step"), ("unknown",), 0.50, 0.8),
    )


def run_sparse_routing_benchmark() -> SparseRoutingBenchmark:
    router = DynamicSparseRouter(
        _routes(),
        config=DynamicSparseConfig(warmup_steps=2),
        seed="benchmark",
    )
    initial_density = router.density

    cases = (
        (RoutingContext("math", "numeric", ("arithmetic", "numeric")), "numeric"),
        (RoutingContext("math", "symbolic", ("algebra", "logic")), "symbolic"),
        (RoutingContext("language", "reading", ("retrieval", "evidence")), "reader"),
        (RoutingContext("science", "multi_step", ("decomposition", "verification"), ("decomposition",)), "decomposer"),
    )

    hits = 0
    for context, expected in cases:
        decision = router.select(context, top_k=2)
        if expected in {item.route_id for item in decision.selected}:
            hits += 1
        for _ in range(6):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=(expected, "verifier"),
                    successful_route_id=expected,
                    reward=0.94,
                    verified=True,
                    context=context,
                )
            )

    easy = RoutingContext("language", "reading", ("retrieval",), uncertainty=0.05, novelty=0.05)
    router.select(easy)
    trained_density = router.density

    hard = RoutingContext(
        "science",
        "multi_step",
        ("logic", "verification"),
        ("decomposition", "verification"),
        uncertainty=0.95,
        novelty=0.90,
        verifier_disagreement=0.90,
    )
    high_risk = router.select(hard)
    high_risk_density = router.density

    checks = (
        ("initial_graph_not_too_sparse", initial_density >= 0.25),
        ("initial_graph_not_dense", initial_density <= 0.60),
        ("specialist_routing", hits >= 3),
        ("post_training_sparser", trained_density < initial_density),
        ("high_risk_reopens_graph", high_risk_density >= trained_density),
        ("hard_case_multi_route", len(high_risk.selected) >= 2),
    )
    passed = sum(1 for _, ok in checks if ok)
    return SparseRoutingBenchmark(
        version="fap.1.0.01.dynamic_sparse_benchmark.v1",
        passed=passed,
        total=len(checks),
        score=passed / len(checks),
        initial_density=initial_density,
        trained_density=trained_density,
        high_risk_density=high_risk_density,
        specialist_hits=hits,
        specialist_total=len(cases),
        checks=checks,
    )


if __name__ == "__main__":
    print(run_sparse_routing_benchmark().to_dict())
