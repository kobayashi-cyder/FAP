from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from fap_revision_r001 import Signal, adaptive_budget
from fap_semantic_action_router import SemanticActionRouter
from fap_semantic_memory import SemanticMemoryStore
from fap_sol_gap_controller import MultiIntentPlanner


def bench_ns(iterations: int, fn) -> tuple[float, int]:
    checksum = 0
    start = time.perf_counter_ns()
    for i in range(iterations):
        checksum += int(fn(i))
    elapsed = time.perf_counter_ns() - start
    return elapsed / iterations, checksum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1_000_000)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    n = max(1, args.iterations)

    router = SemanticActionRouter(args.root)

    with tempfile.TemporaryDirectory(prefix="fap_bench_memory_") as td:
        memory = SemanticMemoryStore(Path(td))
        sid = "bench"
        memories = [
            "目標はFAPをC++化することです。",
            "回答は日本語で出力してください。",
            "C++ native core build verified",
            "semantic router verified",
            "WASM UI bridge verified",
            "FAP native memory is bounded",
            "repository agent remains compatibility boundary",
            "Android JNI is a target",
            "dynamic sparse routing is preferred",
            "verification expands under uncertainty",
            "counterexamples open an extra path",
            "semantic routing is data driven",
            "native UI can operate in native only mode",
            "C ABI exposes deterministic decisions",
            "Python remains for compatibility",
            "benchmark compares identical runner hardware",
        ]
        for row in memories:
            memory.absorb_user(sid, "覚えて " + row)

        planner = MultiIntentPlanner()
        warm = min(10_000, n // 10 + 1)
        warm_checksum = 0
        for _ in range(warm):
            b = adaptive_budget(
                [Signal("multi", 0.9, 5), Signal("verify", 0.7, 2)],
                uncertainty=0.65,
                disagreement=True,
            )
            warm_checksum += b.steps
            r = router.match("猫の画像を生成して")
            warm_checksum += len((r or {}).get("route", ""))
            rows = memory.retrieve(sid, "C++ FAP native memory", 4)
            warm_checksum += len(rows)
            warm_checksum += len(planner.detect("今日の天気と今何時か、それと2+2を計算"))

        budget_ns, c1 = bench_ns(
            n,
            lambda i: sum(
                adaptive_budget(
                    [Signal("multi_step", 0.9, (i % 7) + 1), Signal("verification", 0.7, 2)],
                    uncertainty=0.65,
                    disagreement=True,
                ).__dict__.values()
            ),
        )
        routing_ns, c2 = bench_ns(
            n,
            lambda i: len(
                (router.match("猫の画像を生成して" if i & 1 else "image create") or {}).get("route", "")
            ),
        )
        memory_ns, c3 = bench_ns(
            n,
            lambda i: (
                lambda rows: len(rows) + (len(str(rows[0].get("text", ""))) if rows else 0)
            )(memory.retrieve(sid, "C++ FAP native memory" if i & 1 else "日本語 出力 FAP", 4)),
        )
        intent_ns, c4 = bench_ns(
            n,
            lambda i: len(
                planner.detect(
                    "今日の天気と今何時か、それと2+2を計算"
                    if i & 1
                    else "weather and time and 2+2 calculation"
                )
            ),
        )

    result = {
        "runtime": "python",
        "iterations": n,
        "budget_ns_per_op": budget_ns,
        "routing_ns_per_op": routing_ns,
        "memory_ns_per_op": memory_ns,
        "intent_ns_per_op": intent_ns,
        "checksum": warm_checksum + c1 + c2 + c3 + c4,
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
