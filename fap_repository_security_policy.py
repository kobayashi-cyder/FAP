from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import re
from typing import Iterable

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan
from fap_repository_verifier import VerificationCommand


_SAFE_NAME = re.compile(r"^[0-9A-Za-z_.:/@+=,-]{1,4096}$")


@dataclass(frozen=True)
class SecurityFinding:
    code: str
    severity: str
    subject: str


@dataclass(frozen=True)
class RepositorySecurityReport:
    version: str
    allowed: bool
    findings: tuple[SecurityFinding, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositorySecurityPolicy:
    """Fail-closed preflight policy for repository coding boundaries."""

    VERSION = "fap.repository.security_policy.v1"

    def __init__(
        self,
        *,
        allowed_executables: Iterable[str] = (
            "python",
            "python3",
            "python.exe",
            "py",
            "py.exe",
            "pytest",
            "pytest.exe",
        ),
        max_files: int = 32,
        max_commands: int = 16,
    ) -> None:
        self.allowed_executables = frozenset(
            Path(str(x)).name.casefold()
            for x in allowed_executables
            if str(x).strip()
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must not be empty")
        if not 1 <= int(max_files) <= 64:
            raise ValueError("max_files must be in [1, 64]")
        if not 1 <= int(max_commands) <= 32:
            raise ValueError("max_commands must be in [1, 32]")
        self.max_files = int(max_files)
        self.max_commands = int(max_commands)

    def audit(
        self,
        *,
        plan: PatchPlan,
        edits: Iterable[FileEdit] = (),
        commands: Iterable[VerificationCommand] = (),
    ) -> RepositorySecurityReport:
        findings: list[SecurityFinding] = []
        plan_paths = {item.path: item for item in plan.files}
        edit_rows = tuple(edits)
        command_rows = tuple(commands)

        if plan.write_enabled:
            findings.append(SecurityFinding("plan_write_enabled", "fatal", "plan"))
        required = set(plan.required_checks)
        for check in ("sha_precondition", "sandbox_only", "no_direct_main_write"):
            if check not in required:
                findings.append(
                    SecurityFinding("missing_required_check", "fatal", check)
                )
        if len(plan.files) > self.max_files:
            findings.append(SecurityFinding("plan_file_limit_exceeded", "fatal", "plan"))

        seen: set[str] = set()
        for edit in edit_rows:
            path = _safe_path(edit.path, findings)
            if not path:
                continue
            if path in seen:
                findings.append(SecurityFinding("duplicate_edit_path", "fatal", path))
            seen.add(path)
            planned = plan_paths.get(path)
            if planned is None:
                findings.append(SecurityFinding("unplanned_edit_path", "fatal", path))
                continue
            if edit.operation != planned.operation:
                findings.append(SecurityFinding("operation_mismatch", "fatal", path))
            if edit.before_sha256 != planned.before_sha256:
                findings.append(SecurityFinding("sha_precondition_mismatch", "fatal", path))
            if edit.operation in {"modify", "create"} and edit.content is None:
                findings.append(SecurityFinding("missing_edit_content", "fatal", path))
            if edit.operation == "delete" and edit.content is not None:
                findings.append(SecurityFinding("delete_has_content", "fatal", path))

        if len(command_rows) > self.max_commands:
            findings.append(
                SecurityFinding("verification_command_limit_exceeded", "fatal", "commands")
            )
        names: set[str] = set()
        for command in command_rows:
            name = str(command.name or "").strip()
            if not name:
                findings.append(SecurityFinding("empty_command_name", "fatal", "command"))
            elif name in names:
                findings.append(SecurityFinding("duplicate_command_name", "fatal", name))
            names.add(name)

            if not command.argv:
                findings.append(SecurityFinding("empty_command_argv", "fatal", name))
                continue
            executable = Path(command.argv[0]).name.casefold()
            if executable not in self.allowed_executables:
                findings.append(
                    SecurityFinding("executable_not_allowed", "fatal", executable)
                )
            for arg in command.argv:
                value = str(arg)
                if "\x00" in value or len(value) > 4096:
                    findings.append(SecurityFinding("invalid_argv_value", "fatal", name))
                    break
                # Control characters are not valid transport across coding hosts.
                if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in value):
                    findings.append(SecurityFinding("argv_control_character", "fatal", name))
                    break

        allowed = not any(row.severity == "fatal" for row in findings)
        return RepositorySecurityReport(
            version=self.VERSION,
            allowed=allowed,
            findings=tuple(findings),
        )


def _safe_path(raw: str, findings: list[SecurityFinding]) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or "\x00" in value
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
    ):
        findings.append(SecurityFinding("unsafe_repository_path", "fatal", value))
        return ""
    return posix.as_posix()
