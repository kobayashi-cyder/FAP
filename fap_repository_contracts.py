from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryContract:
    """Stable, content-free schema metadata for repository coding boundaries."""

    name: str
    version: str
    required_fields: tuple[str, ...]
    allowed_states: tuple[str, ...] = ()


CODING_RESULT_VERSION = "fap.repository.coding.v1"
HOST_CONTRACT = "fap.repository.host.v1"
VERIFICATION_SELECTION_VERSION = "fap.repository.verification_selector.v1"


CODING_RESULT_CONTRACT = RepositoryContract(
    name="coding_result",
    version=CODING_RESULT_VERSION,
    required_fields=(
        "version",
        "goal",
        "state",
        "plan",
        "context",
        "repair",
        "final_edits",
        "errors",
    ),
    allowed_states=("verified_candidate", "rejected"),
)

HOST_RESPONSE_CONTRACT = RepositoryContract(
    name="host_response",
    version=HOST_CONTRACT,
    required_fields=(
        "contract",
        "state",
        "observation",
        "plan_id",
        "repository_digest",
        "progress",
        "reason",
        "attempts",
        "repairs_used",
        "paths",
    ),
    allowed_states=("verified_candidate", "rejected", "blocked"),
)

VERIFICATION_SELECTION_CONTRACT = RepositoryContract(
    name="verification_selection",
    version=VERIFICATION_SELECTION_VERSION,
    required_fields=(
        "version",
        "plan_id",
        "commands",
        "focused_tests",
        "regression_strategy",
        "warnings",
    ),
)

CONTRACT_REGISTRY = {
    contract.name: contract
    for contract in (
        CODING_RESULT_CONTRACT,
        HOST_RESPONSE_CONTRACT,
        VERIFICATION_SELECTION_CONTRACT,
    )
}


def contract_for(name: str) -> RepositoryContract:
    key = str(name or "").strip()
    try:
        return CONTRACT_REGISTRY[key]
    except KeyError as exc:
        raise ValueError(f"unknown repository contract: {key}") from exc


def require_contract_version(name: str, version: str) -> str:
    contract = contract_for(name)
    actual = str(version or "").strip()
    if actual != contract.version:
        raise ValueError(
            f"unsupported {contract.name} version: {actual or '<empty>'}"
        )
    return contract.version
