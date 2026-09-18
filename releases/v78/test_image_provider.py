import hashlib
import json
import unittest
from image_provider.evidence import record_failure, record_success

class EvidenceTests(unittest.TestCase):
    def test_success_hash_bounds_and_privacy(self):
        payload = b"fixed-image-fixture"
        ev = record_success(adapter="v77-http", provider="test-provider", mime="image/png",
                            width=1, height=1, payload=payload, latency_ms=12.5,
                            max_bytes=len(payload))
        self.assertEqual(ev.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(ev.byte_count, len(payload))
        self.assertEqual(ev.retained_storage_bytes, 0)
        encoded = ev.to_json()
        self.assertNotIn("prompt", encoded.lower())
        self.assertNotIn("secret", encoded.lower())
        self.assertNotIn(payload.decode(), encoded)
        json.loads(encoded)

    def test_boundary_plus_one_rejected(self):
        with self.assertRaises(ValueError):
            record_success(adapter="a", provider="p", mime="image/png", width=2, height=1,
                           payload=b"x", latency_ms=0, max_width=1)
        with self.assertRaises(ValueError):
            record_success(adapter="a", provider="p", mime="image/png", width=1, height=1,
                           payload=b"xx", latency_ms=0, max_bytes=1)

    def test_empty_and_wrong_mime_rejected(self):
        for mime, payload in (("text/plain", b"x"), ("image/png", b"")):
            with self.assertRaises(ValueError):
                record_success(adapter="a", provider="p", mime=mime, width=1, height=1,
                               payload=payload, latency_ms=0)

    def test_failure_cannot_claim_validated(self):
        with self.assertRaises(ValueError):
            record_failure(adapter="a", provider="p", outcome="validated", latency_ms=1)
        ev = record_failure(adapter="a", provider="p", outcome="backend-unavailable", latency_ms=1)
        self.assertEqual(ev.byte_count, 0)
        self.assertIsNone(ev.sha256)

if __name__ == "__main__":
    unittest.main()
