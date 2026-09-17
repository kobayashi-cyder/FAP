from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence_gate import EvidenceGate, EvidencePolicy
from .operational_ledger import OperationalLedger
from .request_queue import SkillFactoryRequestQueue
from .v59_operational import V59OperationalPlanner, load_jsonl


def main(argv=None):
    ap = argparse.ArgumentParser(description="FAP V61: verified V59 outcomes -> gated autonomous capability request")
    ap.add_argument("v59_log_jsonl")
    ap.add_argument("--state", default="fap_v61_operational.sqlite3")
    ap.add_argument("--out", default="v61_capability_decision.json")
    ap.add_argument("--request-queue", default="")
    ap.add_argument("--audit-fraction", type=float, default=0.20)
    ap.add_argument("--min-verified", type=int, default=20)
    ap.add_argument("--min-failures", type=int, default=3)
    ap.add_argument("--min-family", type=int, default=5)
    ap.add_argument("--min-failure-rate", type=float, default=0.20)
    ns = ap.parse_args(argv)

    ledger = OperationalLedger(ns.state, audit_fraction=ns.audit_fraction)
    gate = EvidenceGate(EvidencePolicy(
        min_verified_cases=ns.min_verified,
        min_cluster_failures=ns.min_failures,
        min_family_cases=ns.min_family,
        min_failure_rate=ns.min_failure_rate,
    ))
    queue = SkillFactoryRequestQueue(ns.request_queue) if ns.request_queue else None
    planner = V59OperationalPlanner(ledger, evidence_gate=gate, request_queue=queue)
    report = planner.ingest_and_plan(load_jsonl(ns.v59_log_jsonl))
    Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
