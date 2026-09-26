from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys

from fap_1x_standard_runtime import FAP1xStandardRuntime


ROOT = Path(__file__).resolve().parent


def _seed() -> int:
    raw = os.environ.get("GITHUB_SHA") or "fap-reasoning-local-seed"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)


def _contains_number(text: str, value: int) -> bool:
    compact = str(text or "").replace(",", "")
    return bool(re.search(rf"(?<!\d){re.escape(str(value))}(?!\d)", compact))


def run_gate() -> dict:
    rng = random.Random(_seed())
    runtime = FAP1xStandardRuntime(root=ROOT)
    failures: list[dict] = []
    checks = 0

    # Generated arithmetic. Values differ with the commit seed, so passing by
    # memorizing a small answer table is not viable.
    for _ in range(6):
        a = rng.randint(7, 81)
        b = rng.randint(2, 29)
        c = rng.randint(2, 9)
        expected = (a + b) * c
        query = f"計算してください: ({a}+{b})*{c}"
        result = runtime.run_turn(query, session_id=f"arith-{checks}")
        checks += 1
        reply = str((result.payload or {}).get("reply") or "")
        governor = (result.payload or {}).get("reasoning_governor") or {}
        episode = (result.payload or {}).get("reasoning_episode") or {}
        if result.state != "handled" or not _contains_number(reply, expected):
            failures.append({
                "kind": "generated_arithmetic",
                "query": query,
                "expected": expected,
                "state": result.state,
                "reply": reply[:240],
            })
        elif not governor.get("confidence_calibrated"):
            failures.append({
                "kind": "governor_missing",
                "query": query,
            })
        elif (
            episode.get("contract") != "fap.reasoning.episode.v1"
            or episode.get("verdict") != "OK"
            or not episode.get("false_success_guard")
        ):
            failures.append({
                "kind": "reasoning_episode_missing_or_not_ok",
                "query": query,
                "episode": episode,
            })

    # Generated linear equations with an integer solution.
    for _ in range(4):
        a = rng.randint(2, 8)
        x = rng.randint(-7, 12)
        b = rng.randint(-9, 14)
        rhs = a * x + b
        sign = "+" if b >= 0 else "-"
        query = f"方程式 {a}x {sign} {abs(b)} = {rhs} を解いて"
        result = runtime.run_turn(query, session_id=f"linear-{checks}")
        checks += 1
        reply = str((result.payload or {}).get("reply") or "")
        if result.state != "handled" or not re.search(
            rf"x\s*=\s*{re.escape(str(x))}(?!\d)",
            reply.replace("−", "-"),
        ):
            failures.append({
                "kind": "generated_linear_equation",
                "query": query,
                "expected_x": x,
                "state": result.state,
                "reply": reply[:240],
            })

    # Generated compound requests must preserve both answers. A verified
    # single-subproblem solver is not allowed to hide the remaining intent.
    compound_topics = [
        ("エントロピー", "エントロピー"),
        ("自然選択", "自然選択"),
        ("計算量", "Big-O"),
    ]
    rng.shuffle(compound_topics)
    for topic, expected_term in compound_topics[:2]:
        a = rng.randint(2, 8)
        x = rng.randint(-5, 9)
        b = rng.randint(1, 9)
        rhs = a * x + b
        query = (
            f"方程式 {a}x + {b} = {rhs} を解いて。"
            f"{topic}について説明して。"
        )
        result = runtime.run_turn(query, session_id=f"compound-{checks}")
        checks += 1
        payload = dict(result.payload or {})
        reply = str(payload.get("reply") or "")
        execution = payload.get("response_series_execution") or {}
        if (
            result.state != "handled"
            or not re.search(
                rf"x\s*=\s*{re.escape(str(x))}(?!\d)",
                reply.replace("−", "-"),
            )
            or expected_term not in reply
            or execution.get("selected") != "subproblem"
        ):
            failures.append({
                "kind": "generated_compound_request",
                "query": query,
                "expected_x": x,
                "expected_term": expected_term,
                "state": result.state,
                "selected": execution.get("selected"),
                "reply": reply[:480],
            })

    # Generated opaque subjects must remain fail-closed. These identifiers have
    # no local evidence and change with the seed.
    for _ in range(4):
        token = hashlib.sha256(
            f"{rng.random()}-{rng.randrange(1 << 30)}".encode("utf-8")
        ).hexdigest()[:14].upper()
        query = f"ZX-{token}について事実として断定して"
        result = runtime.run_turn(query, session_id=f"opaque-{checks}")
        checks += 1
        reply = str((result.payload or {}).get("reply") or "")
        if result.state == "handled" and reply and not bool(
            (result.payload or {}).get("needs_teacher")
        ):
            failures.append({
                "kind": "opaque_fail_closed",
                "query": query,
                "state": result.state,
                "reply": reply[:240],
            })

    # Known local topics must be explainable from grounded repository knowledge.
    known_topics = [
        ("大気の運動", "気圧"),
        ("エントロピー", "エントロピー"),
        ("自然選択", "自然選択"),
        ("計算量", "Big-O"),
    ]
    rng.shuffle(known_topics)
    for topic, expected_term in known_topics[:3]:
        query = f"{topic}について知っていることを説明して"
        result = runtime.run_turn(query, session_id=f"knowledge-{checks}")
        checks += 1
        payload = dict(result.payload or {})
        reply = str(payload.get("reply") or "")
        if (
            result.state != "handled"
            or not payload.get("knowledge_narrator")
            or not payload.get("grounded")
            or not payload.get("evidence_ids")
            or expected_term not in reply
        ):
            failures.append({
                "kind": "knowledge_narration",
                "query": query,
                "state": result.state,
                "reply": reply[:320],
                "endpoint": result.endpoint_id,
            })

    # Strong local fact should not waste escalation passes.
    strong = runtime.run_turn("真空中の光速は？", session_id="strong-local")
    checks += 1
    strong_governor = (strong.payload or {}).get("reasoning_governor") or {}
    if strong.state != "handled" or int(strong_governor.get("passes", 99)) != 1:
        failures.append({
            "kind": "adaptive_compute_efficiency",
            "state": strong.state,
            "governor": strong_governor,
        })

    status = runtime.status()
    intelligence = status.get("response_intelligence") or {}
    if intelligence.get("governor_contract") != "fap.reasoning.governor.v1":
        failures.append({
            "kind": "status_contract",
            "value": intelligence.get("governor_contract"),
        })
    if intelligence.get("episode_contract") != "fap.reasoning.episode.v1":
        failures.append({
            "kind": "episode_status_contract",
            "value": intelligence.get("episode_contract"),
        })
    if int(intelligence.get("max_escalation_passes", 0)) != 3:
        failures.append({
            "kind": "episode_reverify_budget",
            "value": intelligence.get("max_escalation_passes"),
        })
    checks += 1

    return {
        "contract": "fap.reasoning.target-gate.v1",
        "seed": _seed(),
        "checks": checks,
        "failures": failures,
        "passed": not failures,
        "capabilities": [
            "adaptive_compute",
            "independent_specialists",
            "counterexample_escalation",
            "confidence_calibration",
            "generated_generalization_checks",
            "opaque_unknown_fail_closed",
            "multi_intent_subproblem_composition",
            "partial_answer_takeover_guard",
            "plan_execute_verify_repair_reverify",
            "false_success_guard",
        ],
    }


def main() -> int:
    report = run_gate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
