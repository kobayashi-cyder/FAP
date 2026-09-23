from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


@dataclass(frozen=True)
class TransactionMember:
    path: str
    operation: str
    before_sha256: str
    content_sha256: str | None


@dataclass(frozen=True)
class RepositoryEditTransaction:
    version: str
    plan_id: str
    digest: str
    members: tuple[TransactionMember, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryTransactionBuilder:
    """Validate and fingerprint a complete set of planned repository mutations."""

    VERSION = "fap.repository.transaction.v1"

    def build(
        self,
        plan: PatchPlan,
        edits: Iterable[FileEdit],
        *,
        require_all_mutations: bool = True,
    ) -> RepositoryEditTransaction:
        rows = tuple(edits)
        if not rows:
            raise ValueError("at least one edit is required")
        planned = {
            item.path: item
            for item in plan.files
            if item.operation in {"modify", "create", "delete"}
        }
        seen: set[str] = set()
        members: list[TransactionMember] = []
        for edit in rows:
            if edit.path in seen:
                raise ValueError(f"duplicate transaction path: {edit.path}")
            seen.add(edit.path)
            expected = planned.get(edit.path)
            if expected is None:
                raise ValueError(f"unplanned transaction path: {edit.path}")
            if edit.operation != expected.operation:
                raise ValueError(f"operation mismatch: {edit.path}")
            if edit.before_sha256 != expected.before_sha256:
                raise ValueError(f"before hash mismatch: {edit.path}")
            if edit.operation in {"create", "modify"} and edit.content is None:
                raise ValueError(f"content required: {edit.path}")
            if edit.operation == "delete" and edit.content is not None:
                raise ValueError(f"delete content must be empty: {edit.path}")
            members.append(TransactionMember(
                path=edit.path,
                operation=edit.operation,
                before_sha256=edit.before_sha256,
                content_sha256=(sha256(edit.content.encode("utf-8")).hexdigest() if edit.content is not None else None),
            ))
        if require_all_mutations:
            missing = sorted(set(planned) - seen)
            if missing:
                raise ValueError("transaction missing planned mutations: " + ",".join(missing))
        canonical = tuple(sorted(members, key=lambda x: x.path))
        raw = json.dumps([asdict(row) for row in canonical], sort_keys=True, separators=(",", ":"))
        digest = sha256(f"{plan.plan_id}\n{raw}".encode("utf-8")).hexdigest()
        return RepositoryEditTransaction(self.VERSION, plan.plan_id, digest, canonical)

    @staticmethod
    def equivalent(left: RepositoryEditTransaction, right: RepositoryEditTransaction) -> bool:
        return left.plan_id == right.plan_id and left.digest == right.digest and left.members == right.members
