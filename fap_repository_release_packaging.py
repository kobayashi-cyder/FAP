from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable


_BRANCH = re.compile(r"^horiz/coding-[0-9A-Za-z._/-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class IntegrationWorkstream:
    branch: str
    head_sha: str
    pr_number: int
    ci_conclusion: str
    changed_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegrationManifest:
    version: str
    release_line: str
    base_sha: str
    digest: str
    workstreams: tuple[IntegrationWorkstream, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryIntegrationManifestBuilder:
    """Build a content-free manifest for selected horizontal coding workstreams."""

    VERSION = "fap.repository.integration_manifest.v1"

    def build(
        self,
        *,
        release_line: str,
        base_sha: str,
        workstreams: Iterable[IntegrationWorkstream],
        require_green: bool = True,
    ) -> IntegrationManifest:
        release_line = str(release_line or "").strip()
        if not re.fullmatch(r"\d+\.\d+", release_line):
            raise ValueError("release_line must look like 87.81")
        base_sha = str(base_sha or "").strip().lower()
        if not _SHA.fullmatch(base_sha):
            raise ValueError("base_sha must be a 40-character lowercase hex SHA")

        rows = tuple(workstreams)
        if not rows:
            raise ValueError("at least one workstream is required")
        seen: set[str] = set()
        normalized: list[IntegrationWorkstream] = []
        for row in rows:
            if not _BRANCH.fullmatch(row.branch):
                raise ValueError(f"invalid horizontal branch: {row.branch}")
            if row.branch in seen:
                raise ValueError(f"duplicate horizontal branch: {row.branch}")
            seen.add(row.branch)
            head = str(row.head_sha or "").strip().lower()
            if not _SHA.fullmatch(head):
                raise ValueError(f"invalid head SHA: {row.branch}")
            if int(row.pr_number) <= 0:
                raise ValueError(f"invalid PR number: {row.branch}")
            conclusion = str(row.ci_conclusion or "").strip().casefold()
            if require_green and conclusion != "success":
                raise ValueError(f"workstream CI is not green: {row.branch}")
            files = tuple(sorted(dict.fromkeys(str(x) for x in row.changed_files)))
            normalized.append(
                IntegrationWorkstream(
                    branch=row.branch,
                    head_sha=head,
                    pr_number=int(row.pr_number),
                    ci_conclusion=conclusion,
                    changed_files=files,
                )
            )

        normalized.sort(key=lambda row: row.branch)
        payload = {
            "release_line": release_line,
            "base_sha": base_sha,
            "workstreams": [asdict(row) for row in normalized],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(raw.encode("utf-8")).hexdigest()
        return IntegrationManifest(
            version=self.VERSION,
            release_line=release_line,
            base_sha=base_sha,
            digest=digest,
            workstreams=tuple(normalized),
        )
