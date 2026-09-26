from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from fap_request_deliberation import analyze_request
from fap_response_redundancy import ResponseRedundancyPlanner


@dataclass(frozen=True)
class DeliberationBenchmarkResult:
    version: str
    passed: int
    total: int
    checks: tuple[tuple[str, bool], ...]

    def to_dict(self) -> dict:
        return asdict(self)


def run_benchmark() -> DeliberationBenchmarkResult:
    checks: list[tuple[str, bool]] = []

    simple = analyze_request("仕組みを説明して")
    checks.append(("simple_intent_is_bounded", simple.intent_count == 1))

    complex_text = (
        "この実装を検証してください。"
        "必ず制約を守ってください。"
        "反例があるか確認してください。"
        "さらに、手順と根拠を分けて説明してください。"
    )
    complex_sig = analyze_request(complex_text)
    checks.append(("multi_intent_detected", complex_sig.intent_count >= 4))
    checks.append(("constraint_detected", complex_sig.constraint_count >= 1))
    checks.append(("counterexample_detected", complex_sig.counterexample))
    checks.append(("verification_pressure_raised", complex_sig.verification_pressure >= 0.45))
    checks.append(("verification_failure_class", "verification" in complex_sig.failure_classes))

    corrected = analyze_request(
        "前の回答は違う。修正して再検討してください。",
        history=(
            {"role": "user", "text": "最初の条件"},
            {"role": "assistant", "text": "最初の回答"},
        ),
    )
    checks.append(("correction_requests_repair", "repair" in corrected.failure_classes))
    checks.append(("history_pressure_present", corrected.history_pressure > 0.0))

    coding = analyze_request("GitHubのPython実装を修正して検証してください")
    checks.append(("coding_family_detected", coding.task_family == "coding"))
    checks.append(("repository_change_form", coding.task_form == "repository_change"))

    planner = ResponseRedundancyPlanner()
    simple_plan = planner.plan(
        "仕組みを説明して",
        uncertainty=0.05,
        confidence=0.92,
        intent_count=simple.intent_count,
        has_route=True,
    )
    complex_plan = planner.plan(
        complex_text,
        uncertainty=complex_sig.verification_pressure,
        confidence=0.55,
        disagreement=True,
        counterexample=complex_sig.counterexample,
        route_candidates=4,
        verification_depth=4,
        retries=1,
        intent_count=complex_sig.intent_count,
        has_route=True,
    )
    checks.append(("complex_request_gets_more_lanes", complex_plan.active_lanes > simple_plan.active_lanes))

    front_roles = {lane.role for lane in complex_plan.lanes[:6]}
    checks.append(("verification_roles_move_forward", bool(front_roles & {"verifier", "evidence"})))
    checks.append(("counterexample_moves_forward", "counterexample" in front_roles))
    checks.append(("constraints_move_forward", "constraints" in front_roles))

    passed = sum(1 for _name, ok in checks if ok)
    return DeliberationBenchmarkResult(
        version="fap.1.0.01.deliberation.r009",
        passed=passed,
        total=len(checks),
        checks=tuple(checks),
    )


def main() -> int:
    result = run_benchmark()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed == result.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
