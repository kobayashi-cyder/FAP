from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity.primitive_registry_validation import validate_primitive_registry_payload


def record(stage="shadow", transitions=None, shadow=1):
    transitions = transitions or ["candidate", "testing", "shadow"]
    return {
        "primitive_id": "primitive:0123456789abcdef",
        "name": "trim",
        "stage": stage,
        "candidate": {"primitive_id": "primitive:0123456789abcdef", "name": "trim"},
        "evidence": {"transitions": transitions, "shadow_successes": shadow},
    }


class PrimitiveRegistryValidationTests(unittest.TestCase):
    def test_valid_shadow_record_is_accepted(self):
        payload = {"schema": "fap.primitive-registry.v1", "records": [record()]}
        self.assertEqual(validate_primitive_registry_payload(payload)[0]["stage"], "shadow")

    def test_unknown_schema_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_primitive_registry_payload({"schema": "evil", "records": []})

    def test_duplicate_primitive_id_fails_closed(self):
        item = record()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_primitive_registry_payload({"schema": "fap.primitive-registry.v1", "records": [item, copy.deepcopy(item)]})

    def test_candidate_identity_mismatch_fails_closed(self):
        item = record()
        item["candidate"]["primitive_id"] = "primitive:forged"
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_primitive_registry_payload({"schema": "fap.primitive-registry.v1", "records": [item]})

    def test_illegal_direct_activation_fails_closed(self):
        item = record("active", ["candidate", "active"], 3)
        item["evidence"]["promotion"] = "passed"
        with self.assertRaisesRegex(ValueError, "illegal"):
            validate_primitive_registry_payload({"schema": "fap.primitive-registry.v1", "records": [item]})

    def test_active_without_shadow_evidence_fails_closed(self):
        item = record("active", ["candidate", "testing", "shadow", "active"], 2)
        item["evidence"]["promotion"] = "passed"
        with self.assertRaisesRegex(ValueError, "promotion evidence"):
            validate_primitive_registry_payload({"schema": "fap.primitive-registry.v1", "records": [item]})

    def test_valid_active_record_is_accepted(self):
        item = record("active", ["candidate", "testing", "shadow", "active"], 3)
        item["evidence"]["promotion"] = "passed"
        self.assertEqual(validate_primitive_registry_payload({"schema": "fap.primitive-registry.v1", "records": [item]})[0]["stage"], "active")


if __name__ == "__main__":
    unittest.main()
