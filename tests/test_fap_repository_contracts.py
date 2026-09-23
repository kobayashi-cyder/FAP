from __future__ import annotations

from dataclasses import fields
import unittest

from fap_repository_agent import RepositoryCodingResult
from fap_repository_contracts import (
    CODING_RESULT_CONTRACT,
    CODING_RESULT_VERSION,
    CONTRACT_REGISTRY,
    HOST_CONTRACT,
    HOST_RESPONSE_CONTRACT,
    VERIFICATION_SELECTION_CONTRACT,
    VERIFICATION_SELECTION_VERSION,
    contract_for,
    require_contract_version,
    validate_contract_payload,
)
from fap_repository_host import RepositoryHostResponse
from fap_repository_test_selector import (
    RepositoryVerificationSelector,
    VerificationSelection,
)


class RepositoryContractTests(unittest.TestCase):
    def test_registry_has_unique_names_and_versions(self) -> None:
        self.assertEqual(
            set(CONTRACT_REGISTRY),
            {"coding_result", "host_response", "verification_selection"},
        )
        versions = [contract.version for contract in CONTRACT_REGISTRY.values()]
        self.assertEqual(len(versions), len(set(versions)))
        self.assertTrue(
            all(version.startswith("fap.repository.") for version in versions)
        )

    def test_contract_shapes_match_public_dataclasses(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(RepositoryCodingResult)),
            CODING_RESULT_CONTRACT.required_fields,
        )
        self.assertEqual(
            tuple(field.name for field in fields(RepositoryHostResponse)),
            HOST_RESPONSE_CONTRACT.required_fields,
        )
        self.assertEqual(
            tuple(field.name for field in fields(VerificationSelection)),
            VERIFICATION_SELECTION_CONTRACT.required_fields,
        )

    def test_existing_runtime_versions_use_shared_contract_constants(self) -> None:
        self.assertEqual(CODING_RESULT_CONTRACT.version, CODING_RESULT_VERSION)
        self.assertEqual(HOST_RESPONSE_CONTRACT.version, HOST_CONTRACT)
        self.assertEqual(
            RepositoryVerificationSelector.VERSION,
            VERIFICATION_SELECTION_VERSION,
        )

    def test_version_gate_is_fail_closed(self) -> None:
        self.assertEqual(
            require_contract_version("coding_result", CODING_RESULT_VERSION),
            CODING_RESULT_VERSION,
        )
        self.assertIs(contract_for("host_response"), HOST_RESPONSE_CONTRACT)
        with self.assertRaises(ValueError):
            require_contract_version(
                "coding_result",
                "fap.repository.coding.v999",
            )
        with self.assertRaises(ValueError):
            contract_for("missing")

    def test_payload_validation_rejects_missing_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing host_response fields"):
            validate_contract_payload(
                "host_response",
                {
                    "contract": HOST_CONTRACT,
                    "state": "blocked",
                },
            )

    def test_payload_validation_rejects_bad_version_and_state(self) -> None:
        payload = {
            field: None for field in HOST_RESPONSE_CONTRACT.required_fields
        }
        payload.update(
            {
                "contract": "fap.repository.host.v999",
                "state": "blocked",
            }
        )
        with self.assertRaisesRegex(ValueError, "unsupported host_response version"):
            validate_contract_payload("host_response", payload)

        payload["contract"] = HOST_CONTRACT
        payload["state"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unsupported host_response state"):
            validate_contract_payload("host_response", payload)

    def test_payload_validation_allows_additive_fields(self) -> None:
        payload = {
            field: None
            for field in VERIFICATION_SELECTION_CONTRACT.required_fields
        }
        payload.update(
            {
                "version": VERIFICATION_SELECTION_VERSION,
                "extra_future_field": {"safe": True},
            }
        )
        self.assertIs(
            validate_contract_payload("verification_selection", payload),
            VERIFICATION_SELECTION_CONTRACT,
        )

    def test_public_serializers_validate_contracts(self) -> None:
        response = RepositoryHostResponse(
            contract=HOST_CONTRACT,
            state="blocked",
            observation="repository coding blocked",
            plan_id="",
            repository_digest="",
            progress=0.0,
            reason="test",
            attempts=0,
            repairs_used=0,
            paths=(),
        )
        self.assertEqual(response.to_dict()["contract"], HOST_CONTRACT)

        selection = VerificationSelection(
            version=VERIFICATION_SELECTION_VERSION,
            plan_id="plan",
            commands=(),
            focused_tests=(),
            regression_strategy="not_required",
            warnings=(),
        )
        self.assertEqual(
            selection.to_dict()["version"],
            VERIFICATION_SELECTION_VERSION,
        )

        bad_response = RepositoryHostResponse(
            contract=HOST_CONTRACT,
            state="unknown",
            observation="bad",
            plan_id="",
            repository_digest="",
            progress=0.0,
            reason="test",
            attempts=0,
            repairs_used=0,
            paths=(),
        )
        with self.assertRaisesRegex(ValueError, "unsupported host_response state"):
            bad_response.to_dict()


if __name__ == "__main__":
    unittest.main()
