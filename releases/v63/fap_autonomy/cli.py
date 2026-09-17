from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .failure_analyzer import FailureClusterAnalyzer
from .models import BenchmarkCase, BenchmarkResult
from .priority_engine import CapabilityPriorityEngine
from .resource_meter import measure_resources


def load_result_jsonl(path: str) -> List[BenchmarkResult]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        case = BenchmarkCase(
            case_id=r["id"], domain=r.get("domain", "unknown"), task=r.get("task", ""),
            expected=r.get("expected"), metadata=r.get("case_metadata", {}),
        )
        rows.append(BenchmarkResult(
            case=case, success=bool(r.get("success", False)), actual=r.get("actual"),
            error=r.get("error", ""), latency_ms=float(r.get("latency_ms", 0.0)),
            teacher_used=bool(r.get("teacher_used", False)), verified=bool(r.get("verified", False)),
            verifier_confidence=float(r.get("verifier_confidence", 0.0)),
            metadata=r.get("metadata", {}),
        ))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="FAP capability-gap analyzer and priority engine")
    ap.add_argument("results_jsonl")
    ap.add_argument("--out", default="capability_report.json")
    ns = ap.parse_args(argv)
    with measure_resources() as metrics:
        rows = load_result_jsonl(ns.results_jsonl)
        analyzer = FailureClusterAnalyzer()
        clusters = analyzer.cluster(rows)
        engine = CapabilityPriorityEngine()
        ranked = engine.rank(engine.from_clusters(clusters, len(rows)))
        report = {
            "cases": len(rows),
            "clusters": [c.to_dict() for c in clusters],
            "priorities": [d.to_dict() for d in ranked],
            "selected": ranked[0].to_dict() if ranked else None,
        }
    report["resources"] = metrics
    Path(ns.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
