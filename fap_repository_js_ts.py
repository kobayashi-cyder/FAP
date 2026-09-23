from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class JsFunctionPatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class JsFunctionBodySpec:
    path: str
    function_name: str
    replacement_body: str


class RepositoryJsFunctionPatcher:
    """Conservative function-declaration body replacement for JS/TS files."""

    VERSION = "fap.repository.js_function_patch.v1"
    _NAME = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

    def patch(
        self,
        source: str,
        *,
        path: str,
        function_name: str,
        replacement_body: str,
    ) -> str:
        if Path(path).suffix.casefold() not in {".js", ".jsx", ".ts", ".tsx"}:
            raise JsFunctionPatchError("path must be JS/TS")
        if not self._NAME.fullmatch(function_name):
            raise JsFunctionPatchError("function_name is invalid")

        pattern = re.compile(
            rf"\b(?:async\s+)?function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
            re.M,
        )
        matches = list(pattern.finditer(source))
        if len(matches) != 1:
            raise JsFunctionPatchError(
                f"expected exactly one function declaration, found {len(matches)}"
            )
        match = matches[0]
        open_brace = source.rfind("{", match.start(), match.end())
        close_brace = _matching_brace(source, open_brace)
        if close_brace is None:
            raise JsFunctionPatchError("function closing brace not found")

        line_start = source.rfind("\n", 0, match.start()) + 1
        indent_match = re.match(r"[ \t]*", source[line_start:match.start()])
        base_indent = indent_match.group(0) if indent_match else ""
        body_indent = base_indent + "  "
        newline = "\r\n" if "\r\n" in source else "\n"
        body = str(replacement_body or "").strip("\r\n")
        if "\x00" in body:
            raise JsFunctionPatchError("NUL is not allowed")
        rendered = ""
        if body:
            rendered = newline.join(
                body_indent + row if row else ""
                for row in body.replace("\r\n", "\n").split("\n")
            )
            rendered = newline + rendered + newline + base_indent
        else:
            rendered = newline + base_indent
        patched = source[: open_brace + 1] + rendered + source[close_brace:]
        # A second structural pass ensures the target still has a balanced body.
        second = list(pattern.finditer(patched))
        if len(second) != 1:
            raise JsFunctionPatchError("patched function declaration became ambiguous")
        second_open = patched.rfind("{", second[0].start(), second[0].end())
        if _matching_brace(patched, second_open) is None:
            raise JsFunctionPatchError("patched function body is unbalanced")
        return patched

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: JsFunctionBodySpec,
    ) -> FileEdit:
        planned = next((x for x in plan.files if x.path == spec.path), None)
        if planned is None or planned.operation != "modify":
            raise JsFunctionPatchError("JS/TS path is not a planned modify")
        full = Path(root).expanduser().resolve() / spec.path
        if not full.is_file() or full.is_symlink():
            raise JsFunctionPatchError("JS/TS source unavailable")
        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise JsFunctionPatchError("STALE_PLAN: source hash changed")
        source = raw.decode("utf-8")
        content = self.patch(
            source,
            path=spec.path,
            function_name=spec.function_name,
            replacement_body=spec.replacement_body,
        )
        return FileEdit(
            path=spec.path,
            operation="modify",
            before_sha256=planned.before_sha256,
            content=content,
        )


def _matching_brace(source: str, open_index: int) -> int | None:
    if open_index < 0 or open_index >= len(source) or source[open_index] != "{":
        return None
    depth = 0
    state = "normal"
    escaped = False
    i = open_index
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "normal":
            if ch == "/" and nxt == "/":
                state = "line_comment"; i += 2; continue
            if ch == "/" and nxt == "*":
                state = "block_comment"; i += 2; continue
            if ch == "'":
                state = "single"; escaped = False
            elif ch == '"':
                state = "double"; escaped = False
            elif ch == "`":
                state = "template"; escaped = False
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
                if depth < 0:
                    return None
        elif state == "line_comment":
            if ch in "\r\n":
                state = "normal"
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "normal"; i += 2; continue
        else:
            quote = {"single": "'", "double": '"', "template": "`"}[state]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                state = "normal"
        i += 1
    return None
