from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import random
import re
from tempfile import TemporaryDirectory

from fap_1x_runtime import FAP1xRuntime


@dataclass(frozen=True)
class E2EResult:
    version: str
    seed: int
    passed: int
    total: int
    score: float
    checks: tuple[tuple[str, bool], ...]

    def to_dict(self) -> dict:
        return asdict(self)


class _CodingResult:
    def __init__(self, state: str):
        self.state = state

    def to_dict(self):
        return {"state": self.state}


class _CodingCoordinator:
    def __init__(self):
        self.goals: list[str] = []

    def run(self, goal, proposer, commands, **kwargs):
        self.goals.append(str(goal))
        return _CodingResult("verified_candidate")


def _seed() -> int:
    raw = os.environ.get("FAP_E2E_SEED", "").strip()
    if raw:
        return int(raw, 0)
    return random.SystemRandom().randrange(1, 2**63)


def run_e2e(seed: int | None = None) -> E2EResult:
    seed = int(_seed() if seed is None else seed)
    rng = random.Random(seed)
    checks: list[tuple[str, bool]] = []

    # 1) Generated verified-tool challenge. The first high-priority route returns
    # an invalid result; the verifier must reject it and the next route must win.
    a = rng.randrange(10, 10000)
    b = rng.randrange(10, 10000)
    runtime = FAP1xRuntime()

    def parse_sum(text: str) -> tuple[int, int]:
        values = [int(x) for x in re.findall(r"-?\d+", text)]
        return values[0], values[1]

    def bad_tool(text, _metadata):
        x, y = parse_sum(text)
        return {"text": str(x + y + 1), "value": x + y + 1, "a": x, "b": y}

    def good_tool(text, _metadata):
        x, y = parse_sum(text)
        return {"text": str(x + y), "value": x + y, "a": x, "b": y}

    verifier = lambda payload: payload.get("value") == payload.get("a") + payload.get("b")
    runtime.register_tool_endpoint("fast", bad_tool, verifier=verifier, priority=2.0)
    runtime.register_tool_endpoint("verified", good_tool, verifier=verifier, priority=1.0)
    tool = runtime.tool_turn(f"sum {a} {b}")
    checks.append(("verified_tool_fallback", tool.endpoint_id == "verified" and tool.payload.get("value") == a + b))
    checks.append(("rejected_route_visible", any(x.state == "rejected" for x in tool.attempts)))

    # 2) Long-session history must be present but bounded.
    history_runtime = FAP1xRuntime(max_history_messages=8)

    def history_handler(request, _budget):
        return {"ok": True, "text": str(len(request.history))}

    history_runtime.register_endpoint("history", history_handler)
    rounds = rng.randrange(5, 10)
    observed = []
    for i in range(rounds):
        observed.append(int(history_runtime.chat(f"turn-{i}", session_id="history")))
    snap = history_runtime.session_snapshot("history")
    checks.append(("history_progresses", observed[0] == 0 and max(observed) >= 2))
    checks.append(("history_bounded", len(snap) == 8))

    # 3) Generated semantic memory must survive across turns and remain isolated.
    token = f"K{rng.randrange(10**8, 10**9)}"
    other = f"Q{rng.randrange(10**8, 10**9)}"
    with TemporaryDirectory() as root:
        memory_runtime = FAP1xRuntime(memory_root=root)

        def memory_handler(request, _budget):
            memory = tuple((request.metadata or {}).get("memory_context", ()))
            return {"ok": True, "text": " | ".join(memory)}

        memory_runtime.register_endpoint("memory", memory_handler)
        memory_runtime.chat(f"合言葉は{token}", session_id="alpha")
        memory_runtime.chat(f"合言葉は{other}", session_id="beta")
        alpha = memory_runtime.chat("合言葉を覚えている？", session_id="alpha")
        beta = memory_runtime.chat("合言葉を覚えている？", session_id="beta")
        checks.append(("semantic_memory_recall", token in alpha))
        checks.append(("session_memory_isolation", other not in alpha and token not in beta))

    # 4) Coding work must travel through the same dispatch contract.
    coordinator = _CodingCoordinator()
    coding_runtime = FAP1xRuntime()
    coding_runtime.register_repository_coding_endpoint(
        "repo-coder",
        coordinator,
        proposer=object(),
        commands=("compile", "focused-tests"),
    )
    path = f"module_{rng.randrange(1000, 9999)}.py"
    goal = f"fix {path}"
    coding = coding_runtime.coding_turn(goal)
    checks.append((
        "coding_common_dispatch",
        coding.state == "handled"
        and coding.endpoint_id == "repo-coder"
        and coordinator.goals == [goal],
    ))

    # 5) Generated specialist route, independent of any fixed benchmark answer.
    route_runtime = FAP1xRuntime()
    marker = f"special-{rng.randrange(10**6, 10**7)}"
    route_runtime.register_text_endpoint(
        "general",
        lambda _text: "general",
        probe=lambda _text: 0.15,
        capabilities=("general",),
    )
    route_runtime.register_text_endpoint(
        "specialist",
        lambda text: marker if marker in text else "miss",
        probe=lambda text: 0.95 if marker in text else 0.0,
        capabilities=("specialized", "verification"),
    )
    routed = route_runtime.run_turn(
        f"use {marker}",
        metadata={"required_capabilities": ("specialized",)},
    )
    checks.append(("generated_specialist_route", routed.endpoint_id == "specialist"))

    passed = sum(1 for _name, ok in checks if ok)
    return E2EResult(
        version="fap.1.0.01.e2e.v1",
        seed=seed,
        passed=passed,
        total=len(checks),
        score=passed / max(1, len(checks)),
        checks=tuple(checks),
    )


def main() -> int:
    result = run_e2e()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed == result.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
