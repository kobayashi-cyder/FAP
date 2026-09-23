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


if __name__ == "__main__":
    unittest.main()
