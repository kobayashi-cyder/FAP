from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from fap_repository_agent import RepositoryCodingResult
from fap_repository_promotion import PromotionReport


SCHEMA = "fca-fap.exchange.v1"
CAPABILITY = "repository_coding_verified_candidate"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_CONSTRAINTS = (
    "Provenance only: this capsule contains no source code, replacement text, excerpts, diffs, or command output.",
    "FCA must not execute or activate code from this capsule.",
    "FCA connectome selection and reward-plasticity controller remain authoritative.",
    "Independent FCA evidence is required before exchange acceptance or any capability adaptation.",
    "No automatic branch promotion, push, pull request, merge, or main update is authorized by this capsule.",
)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _seal(raw: dict[str, Any]) -> dict[str, Any]:
    body = dict(raw)
    body.pop("digest", None)
    sealed = dict(body)
    sealed["digest"] = sha256(_canonical(body)).hexdigest()
    return sealed


def build_repository_evidence_capsule(
    result: RepositoryCodingResult,
    *,
    source_commit: str,
    promotion: PromotionReport | None = None,
) -> dict[str, Any]:
    """Export inert FAP repository-coding evidence for FCA.

    The capsule intentionally excludes prompts, source excerpts, edit content,
    diffs, command argv and command output. It carries only provenance, hashes,
    bounded verification facts and constraints.
    """
    commit = str(source_commit or "").strip().lower()
    if not HEX40.fullmatch(commit):
        raise ValueError("source_commit must be a 40-char lowercase git sha")
    if result.version != "fap.repository.coding.v1":
        raise ValueError(f"unsupported coding result version: {result.version}")
    if result.state != "verified_candidate" or result.repair is None:
        raise ValueError("only verified repository coding results may be exported")
    if result.repair.state != "verified_candidate" or not result.repair.attempts:
        raise ValueError("verified repair evidence is required")

    final_attempt = result.repair.attempts[-1]
    execution = final_attempt.execution
    verification = final_attempt.verification
    if execution.state != "applied_in_sandbox":
        raise ValueError("final execution was not applied in sandbox")
    if verification.state != "verified_candidate":
        raise ValueError("final verification is not verified_candidate")
    if execution.plan_id != result.plan.plan_id:
        raise ValueError("execution plan provenance mismatch")
    if verification.plan_id != result.plan.plan_id:
        raise ValueError("verification plan provenance mismatch")

    files = [
        {
            "path": row.path,
            "operation": row.operation,
            "before_sha256": row.before_sha256,
            "after_sha256": row.after_sha256,
        }
        for row in sorted(execution.files, key=lambda x: x.path)
    ]
    if not files:
        raise ValueError("verified execution contains no changed files")

    command_evidence = [
        {
            "name": row.name,
            "phase": row.phase,
            "passed": bool(row.passed),
            "returncode": row.returncode,
            "timed_out": bool(row.timed_out),
            "output_limited": bool(row.output_limited),
        }
        for row in verification.commands
    ]

    promotion_evidence: dict[str, Any] | None = None
    if promotion is not None:
        if promotion.plan_id != result.plan.plan_id:
            raise ValueError("promotion plan provenance mismatch")
        if promotion.state != "candidate_branch_created":
            raise ValueError("only successful candidate-branch promotion may be attached")
        if not promotion.branch or not promotion.commit_sha:
            raise ValueError("promotion evidence is incomplete")
        promotion_evidence = {
            "state": promotion.state,
            "branch": promotion.branch,
            "commit_sha": promotion.commit_sha,
            "base_commit": promotion.base_commit,
        }

    mechanism = {
        "contract": result.version,
        "plan_contract": result.plan.version,
        "verification_contract": verification.version,
        "plan_id": result.plan.plan_id,
        "repository_digest": result.plan.task.repository_digest,
        "goal_sha256": sha256(result.goal.encode("utf-8")).hexdigest(),
        "files": files,
        "provider_boundary": "declarative_file_edits_only",
        "control_pattern": "reader_planner_executor_verifier_bounded_repair",
    }
    evidence: dict[str, Any] = {
        "status": "verified_candidate",
        "repair_contract": result.repair.version,
        "attempt_count": len(result.repair.attempts),
        "repairs_used": result.repair.repairs_used,
        "final_execution_state": execution.state,
        "final_verification_state": verification.state,
        "static_passed": bool(verification.static_passed),
        "commands": command_evidence,
    }
    if promotion_evidence is not None:
        evidence["promotion"] = promotion_evidence

    raw = {
        "schema": SCHEMA,
        "source_project": "FAP",
        "source_commit": commit,
        "capability": CAPABILITY,
        "mechanism": mechanism,
        "evidence": evidence,
        "constraints": list(DEFAULT_CONSTRAINTS),
    }
    sealed = _seal(raw)
    validate_repository_evidence_capsule(sealed)
    return sealed


def validate_repository_evidence_capsule(raw: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        raise ValueError("capsule must be an object")
    if raw.get("schema") != SCHEMA:
        raise ValueError("unsupported exchange schema")
    if raw.get("source_project") != "FAP":
        raise ValueError("repository coding capsule must originate from FAP")
    source_commit = str(raw.get("source_commit", "")).strip().lower()
    if not HEX40.fullmatch(source_commit):
        raise ValueError("invalid FAP source commit")
    if raw.get("capability") != CAPABILITY:
        raise ValueError("unsupported repository coding capability")

    mechanism = raw.get("mechanism")
    evidence = raw.get("evidence")
    constraints = raw.get("constraints")
    if not isinstance(mechanism, dict) or not isinstance(evidence, dict):
        raise ValueError("mechanism and evidence are required")
    if not isinstance(constraints, list) or not all(isinstance(x, str) for x in constraints):
        raise ValueError("constraints must be a list of strings")

    supplied = str(raw.get("digest", "")).strip().lower()
    body = dict(raw)
    body.pop("digest", None)
    calculated = sha256(_canonical(body)).hexdigest()
    if supplied != calculated:
        raise ValueError("exchange capsule digest mismatch")

    if mechanism.get("contract") != "fap.repository.coding.v1":
        raise ValueError("unsupported repository coding contract")
    if mechanism.get("plan_contract") != "fap.repository.plan.v1":
        raise ValueError("unsupported repository plan contract")
    if evidence.get("status") != "verified_candidate":
        raise ValueError("capsule is not verified_candidate evidence")

    plan_id = str(mechanism.get("plan_id", "")).lower()
    repository_digest = str(mechanism.get("repository_digest", "")).lower()
    goal_digest = str(mechanism.get("goal_sha256", "")).lower()
    if not HEX64.fullmatch(plan_id):
        raise ValueError("invalid plan_id")
    if not HEX64.fullmatch(repository_digest):
        raise ValueError("invalid repository_digest")
    if not HEX64.fullmatch(goal_digest):
        raise ValueError("invalid goal digest")

    files = mechanism.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("verified file evidence is required")
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("file evidence rows must be objects")
        path = str(row.get("path", ""))
        operation = str(row.get("operation", ""))
        before = str(row.get("before_sha256", "")).lower()
        after = str(row.get("after_sha256", "")).lower()
        if not path or path in seen:
            raise ValueError("invalid or duplicate file path evidence")
        seen.add(path)
        if operation not in {"create", "modify", "delete"}:
            raise ValueError("invalid file operation evidence")
        if operation == "create":
            if before or not HEX64.fullmatch(after):
                raise ValueError("invalid create hash evidence")
        elif operation == "delete":
            if not HEX64.fullmatch(before) or after:
                raise ValueError("invalid delete hash evidence")
        else:
            if not HEX64.fullmatch(before) or not HEX64.fullmatch(after):
                raise ValueError("invalid modify hash evidence")

    forbidden = {"content", "replacement", "excerpt", "diff", "output", "argv"}
    found = _find_forbidden_keys(raw, forbidden)
    if found:
        raise ValueError("capsule contains forbidden executable/source payload keys: " + ",".join(found))


def _find_forbidden_keys(value: Any, forbidden: set[str], prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).casefold() in forbidden:
                found.append(path)
            found.extend(_find_forbidden_keys(child, forbidden, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            found.extend(_find_forbidden_keys(child, forbidden, path))
    return found


def capsule_json(raw: dict[str, Any], *, indent: int = 2) -> str:
    validate_repository_evidence_capsule(raw)
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, indent=indent) + "\n"
