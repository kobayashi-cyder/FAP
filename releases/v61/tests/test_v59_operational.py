import tempfile
import unittest
from pathlib import Path
from fap_autonomy.evidence_gate import EvidenceGate, EvidencePolicy
from fap_autonomy.operational_ledger import OperationalLedger
from fap_autonomy.v59_operational import V59OperationalPlanner


class V59OperationalPlannerTests(unittest.TestCase):
    def test_small_fixture_collects_more_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = OperationalLedger(str(Path(td) / "s.db"), audit_fraction=0.0)
            planner = V59OperationalPlanner(ledger)
            report = planner.ingest_and_plan([
                {"turn_id":"1","text":"multi-step percentage word problem","intent":"math","domain":"math","feedback":"bad",
                 "metadata":{"gap_path":["word_problem","quantity_relation","multi_step"]}},
                {"turn_id":"2","text":"another arithmetic","intent":"math","domain":"math","feedback":"good"},
            ])
            self.assertEqual(report["status"], "collect_more_verified_evidence")
            self.assertIsNone(report["skill_factory_request"])

    def test_repeated_verified_failures_emit_non_executable_request(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = OperationalLedger(str(Path(td) / "s.db"), audit_fraction=0.0)
            gate = EvidenceGate(EvidencePolicy(min_verified_cases=10, min_cluster_failures=3, min_family_cases=5, min_failure_rate=0.2))
            planner = V59OperationalPlanner(ledger, evidence_gate=gate)
            rows = []
            for i in range(12):
                rows.append({
                    "turn_id": f"m{i}", "text": "multi-step percentage word problem quantity relation",
                    "intent": "math", "domain": "math", "feedback": "bad" if i < 5 else "good",
                    "teacher_used": i < 4,
                    "metadata": {"gap_path": ["word_problem","quantity_relation","multi_step"]},
                })
            report = planner.ingest_and_plan(rows)
            self.assertEqual(report["status"], "skill_factory_request_ready")
            spec = report["skill_factory_request"]
            self.assertEqual(spec["metadata"]["executable"], False)
            self.assertEqual(spec["gap"], "MATH_GAP")
            self.assertIn("untouched holdout benchmark", " ".join(spec["acceptance_tests"]))
