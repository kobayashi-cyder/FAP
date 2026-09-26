from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .capability_spec import CapabilitySpecBuilder
from .evidence_gate import EvidenceGate
from .failure_analyzer import FailureClusterAnalyzer
from .models import ImprovementBudget
from .operational_ledger import OperationalLedger
from .operational_matrix import OperationalCapabilityMatrix
from .priority_engine import CapabilityPriorityEngine
from .request_queue import SkillFactoryRequestQueue
from .resource_meter import measure_resources
from .reuse_resolver import CapabilityReuseResolver


class V59OperationalPlanner:
    """Verified V59 outcomes -> persistent ledger -> diagnosis -> gated Skill request.

    Audit-bucket rows are intentionally excluded from ranking. This audit bucket is
    *not* the candidate's untouched benchmark holdout; it is simply operational data
    withheld from diagnosis to detect obvious selection bias later.
    """

    def __init__(self, ledger: OperationalLedger, *, analyzer=None, priority_engine=None,
                 evidence_gate=None, spec_builder=None, reuse_resolver=None, matrix_builder=None,
                 request_queue: Optional[SkillFactoryRequestQueue] = None,
                 budget: Optional[ImprovementBudget] = None):
        self.ledger = ledger
        self.analyzer = analyzer or FailureClusterAnalyzer()
        self.priority_engine = priority_engine or CapabilityPriorityEngine()
        self.evidence_gate = evidence_gate or EvidenceGate()
        self.spec_builder = spec_builder or CapabilitySpecBuilder()
        self.reuse_resolver = reuse_resolver or CapabilityReuseResolver(self.analyzer)
        self.matrix_builder = matrix_builder or OperationalCapabilityMatrix(self.analyzer)
        self.request_queue = request_queue
        self.budget = budget or ImprovementBudget()

    def ingest_and_plan(self, rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        with measure_resources() as metrics:
            ingest = self.ledger.ingest_rows(rows)
            diagnostic = self.ledger.results("diagnostic")
            audit = self.ledger.results("audit")
            clusters = self.analyzer.cluster(diagnostic)
            ranked = self.priority_engine.rank(
                self.priority_engine.from_clusters(clusters, len(diagnostic))
            )
            cluster_by_key = {c.key: c for c in clusters}
            selected = ranked[0] if ranked else None
            gate = None
            spec = None
            reuse = None
            queue_result = None
            status = "no_failure_cluster"
            if selected is not None:
                ckey = selected.candidate.metadata["cluster_key"]
                cluster = cluster_by_key[ckey]
                reuse = self.reuse_resolver.assess(selected, diagnostic)
                gate = self.evidence_gate.evaluate(
                    verified_cases=len(diagnostic), cluster=cluster, priority=selected
                )
                if gate.ready:
                    spec = self.spec_builder.build(selected, cluster, self.budget, reuse.to_dict())
                    status = "skill_factory_request_ready"
                    if self.request_queue is not None:
                        queue_result = self.request_queue.enqueue(spec.to_dict())
                        status = "skill_factory_request_queued"
                else:
                    status = "collect_more_verified_evidence"
        return {
            "schema": "fap.v61.operational-capability-decision/2",
            "status": status,
            "ingest": ingest,
            "ledger": self.ledger.counts(),
            "diagnostic_cases": len(diagnostic),
            "clusters": [c.to_dict() for c in clusters],
            "priorities": [d.to_dict() for d in ranked],
            "selected": selected.to_dict() if selected else None,
            "reuse_assessment": reuse.to_dict() if reuse else None,
            "evidence_gate": gate.to_dict() if gate else None,
            "skill_factory_request": spec.to_dict() if spec else None,
            "queue": queue_result,
            "operational_capability_matrix": self.matrix_builder.build(diagnostic),
            "audit_summary": {
                "cases": len(audit),
                "score": (sum(1 for r in audit if r.success) / len(audit)) if audit else None,
                "used_for_ranking": False,
            },
            "resources": metrics,
            "notes": [
                "Only V59-verified outcomes are admitted.",
                "Audit-bucket rows are excluded from capability ranking.",
                "The reuse assessment prefers extending a repeatedly selected existing V59 skill instead of duplicating it.",
                "A ready request is a non-executable specification; generated source still requires the existing Skill Factory safety/sandbox/benchmark lifecycle.",
                "Candidate untouched holdout evaluation remains separate from this operational audit bucket.",
                "Operational capability matrix scores are descriptive verified-outcome rates, not official public benchmark scores.",
            ],
        }


def load_jsonl(path: str):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)
