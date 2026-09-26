from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_creativity import SkillRegistry
from fap_creativity.primitive_registry_validation import validate_primitive_registry_payload


def candidate_blob(name="trim", program=None):
    program = program or [{"op": "strip", "args": []}]
    payload = json.dumps(
        [name, "string", "string", [(x["op"], tuple(x["args"])) for x in program]],
        ensure_ascii=False,
        sort_keys=True,
    )
    pid = "primitive:" + sha256(payload.encode()).hexdigest()[:16]
    return pid, {
        "primitive_id": pid,
        "name": name,
        "input_kind": "string",
        "output_kind": "string",
        "program": copy.deepcopy(program),
        "tests": [
            {
                "value": " x ",
                "expected": "x",
                "boundary": True,
                "label": "boundary",
            }
        ],
        "description": "trim whitespace",
    }


def record(stage="shadow", transitions=None, shadow=1):
    transitions = transitions or ["candidate", "testing", "shadow"]
    pid, candidate = candidate_blob()
    return {
        "primitive_id": pid,
        "name": "trim",
        "stage": stage,
        "candidate": candidate,
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
            validate_primitive_registry_payload(
                {
                    "schema": "fap.primitive-registry.v1",
                    "records": [item, copy.deepcopy(item)],
                }
            )

    def test_candidate_identity_mismatch_fails_closed(self):
        item = record()
        item["candidate"]["primitive_id"] = "primitive:forged"
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )

    def test_changed_program_with_old_id_fails_closed(self):
        item = record()
        item["candidate"]["program"] = [{"op": "upper", "args": []}]
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )

    def test_illegal_direct_activation_fails_closed(self):
        item = record("active", ["candidate", "active"], 3)
        item["evidence"]["promotion"] = "passed"
        with self.assertRaisesRegex(ValueError, "illegal"):
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )

    def test_active_without_shadow_evidence_fails_closed(self):
        item = record("active", ["candidate", "testing", "shadow", "active"], 2)
        item["evidence"]["promotion"] = "passed"
        with self.assertRaisesRegex(ValueError, "promotion evidence"):
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )

    def test_valid_active_record_is_accepted(self):
        item = record("active", ["candidate", "testing", "shadow", "active"], 3)
        item["evidence"]["promotion"] = "passed"
        self.assertEqual(
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )[0]["stage"],
            "active",
        )

    def test_repeated_shadow_evaluation_history_is_accepted(self):
        item = record(
            "shadow",
            ["candidate", "testing", "shadow", "testing", "shadow"],
            2,
        )
        self.assertEqual(
            validate_primitive_registry_payload(
                {"schema": "fap.primitive-registry.v1", "records": [item]}
            )[0]["stage"],
            "shadow",
        )

    def test_skill_registry_load_invokes_validator(self):
        item = record()
        item["candidate"]["program"] = [{"op": "upper", "args": []}]
        payload = {"schema": "fap.primitive-registry.v1", "records": [item]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest"):
                SkillRegistry(path)

    def test_skill_registry_loads_valid_payload(self):
        item = record()
        payload = {"schema": "fap.primitive-registry.v1", "records": [item]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            registry = SkillRegistry(path)
            self.assertEqual(registry.get(item["primitive_id"])["stage"], "shadow")


if __name__ == "__main__":
    unittest.main()
