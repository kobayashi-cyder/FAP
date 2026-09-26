from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
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
    """Replace one explicitly marked shell/PowerShell/cmd block only."""

    VERSION = "fap.repository.shell_block_edit.v1"
    _SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

    def __init__(self, *, max_body_chars: int = 100_000) -> None:
        if not 1 <= int(max_body_chars) <= 1_000_000:
            raise ValueError("max_body_chars must be in [1, 1000000]")
        self.max_body_chars = int(max_body_chars)

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: ShellBlockSpec,
    ) -> FileEdit:
        path = _safe_shell_path(spec.path)
        if not self._SAFE_NAME.fullmatch(str(spec.name or "")):
            raise ShellBlockEditError("block name is invalid")

        planned = next((x for x in plan.files if x.path == path), None)
        if planned is None or planned.operation != "modify":
            raise ShellBlockEditError("shell path is not a planned modify")

        root_path = Path(root).expanduser().resolve()
        full = (root_path / path).resolve()
        try:
            full.relative_to(root_path)
        except ValueError as exc:
            raise ShellBlockEditError("shell path escapes repository root") from exc
        if not full.is_file() or full.is_symlink():
            raise ShellBlockEditError("shell source unavailable")

        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise ShellBlockEditError("STALE_PLAN: shell source hash changed")
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ShellBlockEditError("shell source is not UTF-8") from exc

        content = self.replace_for_path(
            source,
            path=path,
            name=spec.name,
            body=spec.body,
        )
        return FileEdit(
            path=path,
            operation="modify",
            before_sha256=planned.before_sha256,
            content=content,
        )

    def replace_for_path(
        self,
        source: str,
        *,
        path: str,
        name: str,
        body: str,
    ) -> str:
        return self.replace_block(
            source,
            name=name,
            body=body,
            comment_prefix=_comment_prefix(_safe_shell_path(path)),
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
        if len(str(body or "")) > self.max_body_chars:
            raise ShellBlockEditError("block body exceeds character limit")

        begin = f"{comment_prefix} FAP-BEGIN {name}"
        end = f"{comment_prefix} FAP-END {name}"
        lines = source.splitlines(keepends=True)
        begin_rows = [
            i for i, line in enumerate(lines)
            if line.rstrip("\r\n") == begin
        ]
        end_rows = [
            i for i, line in enumerate(lines)
            if line.rstrip("\r\n") == end
        ]
        if (
            len(begin_rows) != 1
            or len(end_rows) != 1
            or end_rows[0] <= begin_rows[0]
        ):
            raise ShellBlockEditError(
                "expected exactly one ordered FAP block"
            )

        clean = str(body or "").strip("\r\n").replace("\r\n", "\n")
        body_lines = clean.split("\n") if clean else []
        if any(line in {begin, end} for line in body_lines):
            raise ShellBlockEditError("block body must not contain FAP markers")

        start, stop = begin_rows[0], end_rows[0]
        newline = "\r\n" if "\r\n" in source else "\n"
        middle = ""
        if clean:
            middle = clean.replace("\n", newline) + newline
        replacement = begin + newline + middle + end + newline
        result = (
            "".join(lines[:start])
            + replacement
            + "".join(lines[stop + 1 :])
        )

        result_lines = result.splitlines()
        if result_lines.count(begin) != 1 or result_lines.count(end) != 1:
            raise ShellBlockEditError("patched FAP block became ambiguous")
        return result


def _safe_shell_path(raw: object) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or "\x00" in value
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
    ):
        raise ShellBlockEditError("path must be a safe relative shell path")
    normalized = posix.as_posix()
    _comment_prefix(normalized)
    return normalized


def _comment_prefix(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    if suffix in {".sh", ".ps1"}:
        return "#"
    if suffix == ".cmd":
        return "REM"
    raise ShellBlockEditError(
        "supported shell paths are .sh, .ps1 and .cmd"
    )
