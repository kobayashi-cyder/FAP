from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
V70 = ROOT.parents[1] / "v70" / "media_adapters"
V69 = ROOT.parents[1] / "v69" / "interaction"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V70))
sys.path.insert(0, str(V69))

from fap_provider_adapters import CommandJSONClient, ProcessProviderSpec
from fap_provider_probe import CapabilityGate, ProviderCapabilityProbe


PYTHON = Path(sys.executable).resolve()
FIXTURE = (Path(__file__).parent / "fixtures" / "probe_provider.py").resolve()


def probe(mode="healthy", timeout_s=1.0):
    client = CommandJSONClient(
        ProcessProviderSpec(
            executable=str(PYTHON),
            fixed_args=(str(FIXTURE), mode),
            timeout_s=timeout_s,
        )
    )
    return ProviderCapabilityProbe(client).run()


class ProviderProbeTests(unittest.TestCase):
    def test_healthy_provider_capabilities_are_canonical(self):
        result = probe()
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.protocol_version, 1)
        self.assertEqual(result.provider_id, "fixture-all")
        self.assertEqual(result.capabilities, ("image", "stt", "tts"))

    def test_gate_requires_healthy_probe(self):
        gate = CapabilityGate.from_probe(probe())
        self.assertTrue(gate.image)
        self.assertTrue(gate.stt)
        self.assertTrue(gate.tts)
        self.assertTrue(gate.half_duplex_voice)

        bad = CapabilityGate.from_probe(probe("not-ready"))
        self.assertFalse(bad.image)
        self.assertFalse(bad.stt)
        self.assertFalse(bad.tts)
        self.assertFalse(bad.half_duplex_voice)

    def test_subset_enables_voice_without_image(self):
        gate = CapabilityGate.from_probe(probe("subset"))
        self.assertFalse(gate.image)
        self.assertTrue(gate.stt)
        self.assertTrue(gate.tts)
        self.assertTrue(gate.half_duplex_voice)

    def test_wrong_protocol_is_incompatible(self):
        result = probe("wrong-version")
        self.assertEqual(result.status, "incompatible")
        self.assertEqual(result.reason, "protocol_version_mismatch")

    def test_not_ready_is_unavailable_but_preserves_declared_caps(self):
        result = probe("not-ready")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.capabilities, ("image",))
        self.assertEqual(result.reason, "provider_not_ready")

    def test_duplicate_capabilities_fail_closed(self):
        result = probe("duplicate")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "invalid_probe_response")

    def test_unknown_capability_fails_closed(self):
        result = probe("unknown")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "invalid_probe_response")

    def test_timeout_is_unavailable(self):
        result = probe("timeout", timeout_s=0.05)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason, "provider_probe_timeout")

    def test_nonzero_exit_is_error(self):
        result = probe("exit")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "provider_probe_error")


if __name__ == "__main__":
    unittest.main()
