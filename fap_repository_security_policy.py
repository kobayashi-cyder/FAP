from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import sys
from typing import Iterable

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan
from fap_repository_verifier import PHASES, VerificationCommand


_ALLOWED_PLAN_OPERATIONS = frozenset({"inspect", "modify", "create", "delete"})


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
        allowed_executable_paths: Iterable[str] = (sys.executable,),
        max_files: int = 32,
        max_commands: int = 16,
        max_timeout_sec: int = 120,
    ) -> None:
        self.allowed_executables = frozenset(
            Path(str(x)).name.casefold()
            for x in allowed_executables
            if str(x).strip()
        )
        self.allowed_executable_paths = frozenset(
            _resolved_path(x)
            for x in allowed_executable_paths
            if str(x).strip()
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must not be empty")
        if not 1 <= int(max_files) <= 64:
            raise ValueError("max_files must be in [1, 64]")
        if not 1 <= int(max_commands) <= 32:
            raise ValueError("max_commands must be in [1, 32]")
        if not 1 <= int(max_timeout_sec) <= 600:
            raise ValueError("max_timeout_sec must be in [1, 600]")
        self.max_files = int(max_files)
        self.max_commands = int(max_commands)
        self.max_timeout_sec = int(max_timeout_sec)

    def audit(
        self,
        *,
        plan: PatchPlan,
        edits: Iterable[FileEdit] = (),
        commands: Iterable[VerificationCommand] = (),
    ) -> RepositorySecurityReport:
        findings: list[SecurityFinding] = []
        edit_rows = tuple(edits)
        command_rows = tuple(commands)

        if plan.version != "fap.repository.plan.v1":
            findings.append(SecurityFinding("unsupported_plan_version", "fatal", "plan"))
        if plan.status != "ready":
            findings.append(SecurityFinding("plan_not_ready", "fatal", str(plan.status)))
        if plan.write_enabled:
            findings.append(SecurityFinding("plan_write_enabled", "fatal", "plan"))

        required = set(plan.required_checks)
        for check in ("sha_precondition", "sandbox_only", "no_direct_main_write"):
            if check not in required:
                findings.append(
                    SecurityFinding("missing_required_check", "fatal", check)
                )

        if len(plan.files) > self.max_files:
            findings.append(
                SecurityFinding("plan_file_limit_exceeded", "fatal", "plan")
            )
        if len(edit_rows) > self.max_files:
            findings.append(
                SecurityFinding("edit_file_limit_exceeded", "fatal", "edits")
            )

        plan_paths: dict[str, object] = {}
        for planned in plan.files:
            path = _safe_path(planned.path, findings, "plan")
            if not path:
                continue
            if path in plan_paths:
                findings.append(SecurityFinding("duplicate_plan_path", "fatal", path))
            plan_paths[path] = planned
            if planned.operation not in _ALLOWED_PLAN_OPERATIONS:
                findings.append(
                    SecurityFinding("unsupported_plan_operation", "fatal", path)
                )

        seen: set[str] = set()
        for edit in edit_rows:
            path = _safe_path(edit.path, findings, "edit")
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
                findings.append(
                    SecurityFinding("sha_precondition_mismatch", "fatal", path)
                )
            if edit.operation in {"modify", "create"} and edit.content is None:
                findings.append(SecurityFinding("missing_edit_content", "fatal", path))
            if edit.operation == "delete" and edit.content is not None:
                findings.append(SecurityFinding("delete_has_content", "fatal", path))

        if len(command_rows) > self.max_commands:
            findings.append(
                SecurityFinding(
                    "verification_command_limit_exceeded",
                    "fatal",
                    "commands",
                )
            )

        names: set[str] = set()
        for command in command_rows:
            name = str(command.name or "").strip()
            if not name:
                findings.append(
                    SecurityFinding("empty_command_name", "fatal", "command")
                )
            elif name in names:
                findings.append(
                    SecurityFinding("duplicate_command_name", "fatal", name[:120])
                )
            names.add(name)

            if command.phase not in PHASES:
                findings.append(
                    SecurityFinding("unsupported_command_phase", "fatal", name[:120])
                )
            try:
                timeout = int(command.timeout_sec)
            except (TypeError, ValueError):
                timeout = 0
            if not 1 <= timeout <= self.max_timeout_sec:
                findings.append(
                    SecurityFinding("invalid_command_timeout", "fatal", name[:120])
                )

            if not command.argv or len(command.argv) > 32:
                findings.append(
                    SecurityFinding("invalid_command_argv", "fatal", name[:120])
                )
                continue

            executable_raw = str(command.argv[0])
            executable = Path(executable_raw).name.casefold()
            if executable not in self.allowed_executables:
                findings.append(
                    SecurityFinding("executable_not_allowed", "fatal", executable[:120])
                )
            elif _is_path_qualified(executable_raw):
                if _resolved_path(executable_raw) not in self.allowed_executable_paths:
                    findings.append(
                        SecurityFinding(
                            "executable_path_not_allowed",
                            "fatal",
                            executable[:120],
                        )
                    )

            for arg in command.argv:
                value = str(arg)
                if len(value) > 4096 or any(ord(ch) < 32 for ch in value):
                    findings.append(
                        SecurityFinding("invalid_argv_value", "fatal", name[:120])
                    )
                    break

        allowed = not any(row.severity == "fatal" for row in findings)
        return RepositorySecurityReport(
            version=self.VERSION,
            allowed=allowed,
            findings=tuple(findings),
        )


def _safe_path(
    raw: object,
    findings: list[SecurityFinding],
    source: str,
) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or "\x00" in value
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
    ):
        findings.append(
            SecurityFinding(
                "unsafe_repository_path",
                "fatal",
                source,
            )
        )
        return ""
    return posix.as_posix()


def _is_path_qualified(raw: str) -> bool:
    value = str(raw or "")
    return Path(value).is_absolute() or "/" in value or "\\" in value


def _resolved_path(raw: object) -> str:
    return str(Path(str(raw)).expanduser().resolve()).casefold()
