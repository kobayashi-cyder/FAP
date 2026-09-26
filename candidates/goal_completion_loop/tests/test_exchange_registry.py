from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop import ExchangeCapsule, ExchangeEvidence, ExchangeRegistry, ExchangeState


class ExchangeRegistryTests(unittest.TestCase):
    def capsule(self):
        return ExchangeCapsule.from_dict({
            "schema": "fca-fap.exchange.v1",
            "source_project": "FCA",
            "source_commit": "b" * 40,
            "capability": "sparse_gate",
            "mechanism": {"kind": "sparse"},
            "evidence": {"tests": "pass"},
            "constraints": ["shadow first"],
        })

    def test_shadow_then_accept(self):
        cap = self.capsule()
        reg = ExchangeRegistry(shadow_after=1, accept_after=2)
        self.assertEqual(reg.receive(cap), ExchangeState.RECEIVED)
        self.assertEqual(reg.add_evidence(cap.digest, ExchangeEvidence("1", True)), ExchangeState.SHADOW)
        self.assertEqual(reg.add_evidence(cap.digest, ExchangeEvidence("2", True)), ExchangeState.ACCEPTED)
        self.assertEqual(reg.accepted_capabilities(), ("sparse_gate",))

    def test_bad_evidence_rejects(self):
        cap = self.capsule()
        reg = ExchangeRegistry()
        reg.receive(cap)
        self.assertEqual(
            reg.add_evidence(cap.digest, ExchangeEvidence("bad", False)),
            ExchangeState.REJECTED,
        )


if __name__ == "__main__":
    unittest.main()
