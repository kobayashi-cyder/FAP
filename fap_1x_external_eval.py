from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any

from fap_1x_standard_runtime import FAP1xStandardRuntime


@dataclass(frozen=True)
class EvalRow:
    item_id: str
    domain: str
    prediction: str
    confidence: float
    verification_state: str
    correct: bool
    abstained: bool
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("{}:{} is not an object".format(path, line_no))
        rows.append(row)
    return rows


def _git_sha(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _extract_prediction(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    text = str(payload.get("reply") or payload.get("text") or "").strip()
    import re
    match = re.search(r"(?i)Answer\s*:\s*\$?([A-D])\$?", text)
    if match:
        return match.group(1).upper()
    return text


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _correct(prediction: str, answer: Any, mode: str) -> bool:
    pred = str(prediction or "").strip()
    expected = str(answer or "").strip()
    if mode == "mcq":
        return pred.upper() == expected.upper()
    if mode == "numeric":
        try:
            return math.isclose(float(pred), float(expected), rel_tol=1e-9, abs_tol=1e-9)
        except ValueError:
            return False
    return _normalize(prediction) == _normalize(answer)


def _ece(rows: list[EvalRow], bins: int = 10) -> float:
    if not rows:
        return 0.0
    total = len(rows)
    error = 0.0
    for index in range(bins):
        lo = index / bins
        hi = (index + 1) / bins
        bucket = [
            row for row in rows
            if (lo <= row.confidence < hi)
            or (index == bins - 1 and row.confidence == 1.0)
        ]
        if not bucket:
            continue
        acc = sum(row.correct for row in bucket) / len(bucket)
        conf = sum(row.confidence for row in bucket) / len(bucket)
        error += (len(bucket) / total) * abs(acc - conf)
    return error


def _brier(rows: list[EvalRow]) -> float:
    if not rows:
        return 0.0
    return sum((row.confidence - float(row.correct)) ** 2 for row in rows) / len(rows)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[pos]


class IsolatedHoldoutEvaluator:
    """Evaluate prompts while keeping answer keys out of runtime inputs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _ensure_isolated_answer_file(self, path: Path) -> None:
        resolved = path.expanduser().resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            return
        raise ValueError(
            "answer key must live outside the repository tree to reduce benchmark leakage"
        )

    def run(
        self,
        prompts_path: str | Path,
        answers_path: str | Path,
        *,
        memory_root: str | Path | None = None,
    ) -> dict[str, Any]:
        prompts_file = Path(prompts_path).expanduser().resolve()
        answers_file = Path(answers_path).expanduser().resolve()
        self._ensure_isolated_answer_file(answers_file)

        prompts = _load_jsonl(prompts_file)
        answers = _load_jsonl(answers_file)
        answer_map = {str(row["id"]): row for row in answers}
        prompt_ids = [str(row["id"]) for row in prompts]
        if len(prompt_ids) != len(set(prompt_ids)):
            raise ValueError("duplicate prompt ids")
        if set(prompt_ids) != set(answer_map):
            raise ValueError("prompt and answer id sets differ")

        runtime = FAP1xStandardRuntime(
            root=self.root,
            memory_root=memory_root,
        )
        predictions: list[dict[str, Any]] = []

        # Important: this phase never reads answer_map.
        for item in prompts:
            item_id = str(item["id"])
            prompt = str(item["prompt"])
            started = time.perf_counter()
            dispatch = runtime.run_turn(
                prompt,
                session_id="eval-" + item_id,
                metadata={
                    "benchmark_item_id": item_id,
                    "benchmark_domain": str(item.get("domain") or "general"),
                },
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            payload = dict(dispatch.payload or {})
            prediction = _extract_prediction(payload)
            predictions.append(
                {
                    "id": item_id,
                    "domain": str(item.get("domain") or "general"),
                    "prediction": prediction,
                    "confidence": float(payload.get("confidence", 0.0) or 0.0),
                    "verification_state": str(payload.get("verification_state") or ""),
                    "abstained": bool(
                        dispatch.state != "handled"
                        or not prediction
                        or payload.get("verification_state") == "unresolved"
                    ),
                    "latency_ms": elapsed_ms,
                }
            )

        # Scoring is a separate phase after inference has completed.
        rows: list[EvalRow] = []
        for prediction in predictions:
            key = answer_map[prediction["id"]]
            mode = str(key.get("mode") or "exact")
            correct = (
                False
                if prediction["abstained"]
                else _correct(prediction["prediction"], key.get("answer"), mode)
            )
            rows.append(
                EvalRow(
                    item_id=prediction["id"],
                    domain=prediction["domain"],
                    prediction=prediction["prediction"],
                    confidence=max(0.0, min(1.0, prediction["confidence"])),
                    verification_state=prediction["verification_state"],
                    correct=correct,
                    abstained=prediction["abstained"],
                    latency_ms=prediction["latency_ms"],
                )
            )

        by_domain: dict[str, list[EvalRow]] = defaultdict(list)
        for row in rows:
            by_domain[row.domain].append(row)

        latencies = [row.latency_ms for row in rows]
        answered = [row for row in rows if not row.abstained]
        report = {
            "version": "fap.1.0.01.external_eval.v1",
            "commit_sha": _git_sha(self.root),
            "prompt_sha256": _sha256(prompts_file),
            "answer_sha256": _sha256(answers_file),
            "items": len(rows),
            "correct": sum(row.correct for row in rows),
            "accuracy": sum(row.correct for row in rows) / max(1, len(rows)),
            "coverage": len(answered) / max(1, len(rows)),
            "abstention_rate": sum(row.abstained for row in rows) / max(1, len(rows)),
            "answered_accuracy": (
                sum(row.correct for row in answered) / len(answered)
                if answered else 0.0
            ),
            "brier": _brier(rows),
            "ece_10": _ece(rows, 10),
            "latency_ms": {
                "mean": statistics.fmean(latencies) if latencies else 0.0,
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies) if latencies else 0.0,
            },
            "domains": {
                domain: {
                    "items": len(group),
                    "accuracy": sum(row.correct for row in group) / max(1, len(group)),
                    "coverage": sum(not row.abstained for row in group) / max(1, len(group)),
                }
                for domain, group in sorted(by_domain.items())
            },
            "rows": [row.to_dict() for row in rows],
        }
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args(argv)

    report = IsolatedHoldoutEvaluator(args.root).run(args.prompts, args.answers)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
