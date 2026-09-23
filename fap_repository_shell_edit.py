from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class ShellBlockEditError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShellBlockSpec:
    path: str
    name: str
    body: str


class RepositoryShellBlockEditor:
    """Replace an explicitly marked shell/PowerShell/cmd block only."""

    VERSION = "fap.repository.shell_block_edit.v1"
    _SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: ShellBlockSpec,
    ) -> FileEdit:
        if not self._SAFE_NAME.fullmatch(str(spec.name or "")):
            raise ShellBlockEditError("block name is invalid")
        prefix = _comment_prefix(spec.path)
        planned = next((x for x in plan.files if x.path == spec.path), None)
        if planned is None or planned.operation != "modify":
            raise ShellBlockEditError("shell path is not a planned modify")

        full = Path(root).expanduser().resolve() / spec.path
        if not full.is_file() or full.is_symlink():
            raise ShellBlockEditError("shell source unavailable")
        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise ShellBlockEditError("STALE_PLAN: shell source hash changed")
        source = raw.decode("utf-8")
        content = self.replace_block(
            source,
            name=spec.name,
            body=spec.body,
            comment_prefix=prefix,
        )
        return FileEdit(
            path=spec.path,
            operation="modify",
            before_sha256=planned.before_sha256,
            content=content,
        )

    def replace_block(
        self,
        source: str,
        *,
        name: str,
        body: str,
        comment_prefix: str = "#",
    ) -> str:
        if "\x00" in source or "\x00" in body:
            raise ShellBlockEditError("NUL is not allowed")
        if not self._SAFE_NAME.fullmatch(str(name or "")):
            raise ShellBlockEditError("block name is invalid")
        begin = f"{comment_prefix} FAP-BEGIN {name}"
        end = f"{comment_prefix} FAP-END {name}"
        lines = source.splitlines(keepends=True)
        begin_rows = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == begin]
        end_rows = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == end]
        if len(begin_rows) != 1 or len(end_rows) != 1 or end_rows[0] <= begin_rows[0]:
            raise ShellBlockEditError("expected exactly one ordered FAP block")

        start, stop = begin_rows[0], end_rows[0]
        newline = "\r\n" if "\r\n" in source else "\n"
        clean = str(body or "").strip("\r\n").replace("\r\n", "\n")
        middle = ""
        if clean:
            middle = clean.replace("\n", newline) + newline
        replacement = begin + newline + middle + end + newline
        return "".join(lines[:start]) + replacement + "".join(lines[stop + 1 :])


def _comment_prefix(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    if suffix in {".sh", ".ps1"}:
        return "#"
    if suffix == ".cmd":
        return "REM"
    raise ShellBlockEditError("supported shell paths are .sh, .ps1 and .cmd")
