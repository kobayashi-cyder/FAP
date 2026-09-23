from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class MarkdownEditError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarkdownSectionSpec:
    path: str
    heading: str
    body: str
    level: int = 2


class RepositoryMarkdownEditor:
    """Replace one Markdown section while preserving unrelated text."""

    VERSION = "fap.repository.markdown_edit.v1"

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: MarkdownSectionSpec,
    ) -> FileEdit:
        if not 1 <= int(spec.level) <= 6:
            raise MarkdownEditError("heading level must be in [1, 6]")
        if not spec.path.endswith(".md"):
            raise MarkdownEditError("Markdown editor requires a .md path")
        heading = str(spec.heading or "").strip()
        if not heading or "\n" in heading:
            raise MarkdownEditError("heading must be one line")

        planned = next((x for x in plan.files if x.path == spec.path), None)
        if planned is None or planned.operation != "modify":
            raise MarkdownEditError("Markdown path is not a planned modify")

        full = Path(root).expanduser().resolve() / spec.path
        if not full.is_file() or full.is_symlink():
            raise MarkdownEditError("Markdown source unavailable")
        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise MarkdownEditError("STALE_PLAN: Markdown source hash changed")
        source = raw.decode("utf-8")

        content = self.replace_section(
            source,
            heading=heading,
            body=spec.body,
            level=int(spec.level),
        )
        return FileEdit(
            path=spec.path,
            operation="modify",
            before_sha256=planned.before_sha256,
            content=content,
        )

    def replace_section(
        self,
        source: str,
        *,
        heading: str,
        body: str,
        level: int = 2,
    ) -> str:
        prefix = "#" * int(level)
        target = f"{prefix} {heading}"
        lines = source.splitlines(keepends=True)

        starts = [
            i for i, line in enumerate(lines)
            if line.rstrip("\r\n") == target
        ]
        if len(starts) != 1:
            raise MarkdownEditError(
                f"expected exactly one heading {target!r}, found {len(starts)}"
            )
        start = starts[0]
        end = len(lines)
        heading_pattern = re.compile(r"^(#{1,6})\s+")
        for i in range(start + 1, len(lines)):
            match = heading_pattern.match(lines[i])
            if match and len(match.group(1)) <= int(level):
                end = i
                break

        newline = "\r\n" if "\r\n" in source else "\n"
        clean_body = str(body or "").strip("\r\n")
        replacement = target + newline
        if clean_body:
            replacement += newline + clean_body.replace("\r\n", "\n").replace(
                "\n", newline
            ) + newline
        replacement += newline

        return "".join(lines[:start]) + replacement + "".join(lines[end:])
