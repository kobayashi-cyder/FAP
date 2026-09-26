from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable

from fap_repository_executor import (
    ExecutionReport,
    FileEdit,
    RepositoryPatchExecutor,
    SandboxSession,
)
from fap_repository_planner import PatchPlan
from fap_repository_reader import RepositoryReader


PHASES = ("focused", "regression")


@dataclass(frozen=True)
class VerificationCommand:
    name: str
    phase: str
    argv: tuple[str, ...]
    timeout_sec: int = 60
    required: bool = True


@dataclass(frozen=True)
class CommandResult:
    name: str
    phase: str
    argv: tuple[str, ...]
    returncode: int | None
    duration_ms: int
    passed: bool
    timed_out: bool
    output_limited: bool
    output: str
    error: str | None = None


@dataclass(frozen=True)
class VerificationReport:
    version: str
    plan_id: str
    state: str
    static_passed: bool
    commands: tuple[CommandResult, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CandidateAttempt:
    round_index: int
    execution: ExecutionReport
    verification: VerificationReport


@dataclass(frozen=True)
class RepairRunReport:
    version: str
    plan_id: str
    state: str
    repairs_used: int
    attempts: tuple[CandidateAttempt, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


RepairProvider = Callable[
    [tuple[FileEdit, ...], CandidateAttempt],
    Iterable[FileEdit] | None,
]


class RepositoryVerifier:
    """V87.68 verifier for an already-applied V87.67 sandbox candidate.

    Static Python syntax checks use compile() without importing project modules.
    Focused/regression commands are explicit argv vectors, never shell strings.
    Runtime, command count, executable names and captured output are bounded.
    """

    def __init__(
        self,
        *,
        allowed_executables: Iterable[str] | None = None,
        max_commands: int = 8,
        max_timeout_sec: int = 120,
        max_output_bytes: int = 200_000,
        poll_interval_sec: float = 0.02,
        passthrough_env: Iterable[str] = (),
    ) -> None:
        default_allowed = {
            Path(sys.executable).name.casefold(),
            "python",
            "python3",
            "python.exe",
            "py",
            "py.exe",
            "pytest",
            "pytest.exe",
        }
        values = default_allowed if allowed_executables is None else set(allowed_executables)
        self.allowed_executables = frozenset(
            Path(str(x)).name.casefold() for x in values if str(x).strip()
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must not be empty")
        if not 1 <= int(max_commands) <= 32:
            raise ValueError("max_commands must be in [1, 32]")
        if not 1 <= int(max_timeout_sec) <= 600:
            raise ValueError("max_timeout_sec must be in [1, 600]")
        if not 1_000 <= int(max_output_bytes) <= 5_000_000:
            raise ValueError("max_output_bytes must be in [1000, 5000000]")
        if not 0.005 <= float(poll_interval_sec) <= 0.5:
            raise ValueError("poll_interval_sec must be in [0.005, 0.5]")
        self.max_commands = int(max_commands)
        self.max_timeout_sec = int(max_timeout_sec)
        self.max_output_bytes = int(max_output_bytes)
        self.poll_interval_sec = float(poll_interval_sec)
        self.passthrough_env = tuple(dict.fromkeys(str(x) for x in passthrough_env))

    def verify(
        self,
        session: SandboxSession,
        execution: ExecutionReport,
        commands: Iterable[VerificationCommand],
    ) -> VerificationReport:
        if session.closed:
            raise RuntimeError("sandbox session is closed")
        if execution.plan_id != session.plan.plan_id:
            raise ValueError("execution report does not match sandbox plan")
        if execution.state != "applied_in_sandbox":
            return self._reject(
                session.plan.plan_id,
                False,
                (),
                ("candidate_not_applied",) + tuple(execution.errors),
            )

        source_status_before = self._source_status(session)
        command_list = tuple(commands)
        try:
            self._validate_commands(command_list)
        except Exception as exc:
            return self._reject(
                session.plan.plan_id,
                False,
                (),
                (f"command_policy:{type(exc).__name__}:{exc}",),
            )

        static_result = self._static_compile(session, execution)
        results: list[CommandResult] = [static_result]
        if not static_result.passed:
            return self._reject(
                session.plan.plan_id,
                False,
                tuple(results),
                ("static_compile_failed",),
            )

        required_checks = set(session.plan.required_checks)
        focused = tuple(cmd for cmd in command_list if cmd.phase == "focused")
        regression = tuple(cmd for cmd in command_list if cmd.phase == "regression")

        if "focused_tests" in required_checks and not focused:
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("missing_required_focused_tests",),
            )
        if "regression_tests" in required_checks and not regression:
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("missing_required_regression_tests",),
            )

        state = "static_pass"
        for phase, phase_commands, pass_state in (
            ("focused", focused, "focused_test_pass"),
            ("regression", regression, "regression_pass"),
        ):
            if not phase_commands:
                continue
            for command in phase_commands:
                result = self._run_command(session, command)
                results.append(result)
                if command.required and not result.passed:
                    return self._reject(
                        session.plan.plan_id,
                        True,
                        tuple(results),
                        (f"{phase}_command_failed:{command.name}",),
                    )
            state = pass_state

        contamination = self._sandbox_contamination(session, execution)
        if contamination:
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                tuple(contamination),
            )

        source_status_after = self._source_status(session)
        if source_status_after != source_status_before:
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("source_working_tree_changed_during_verification",),
            )
        current_digest = RepositoryReader(
            session.executor.root,
            max_files=1,
            max_total_bytes=1,
            max_file_bytes=1,
            dependency_hops=0,
        ).repository_digest
        if current_digest != session.plan.task.repository_digest:
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("source_repository_digest_changed_during_verification",),
            )

        if "focused_tests" in required_checks and state == "static_pass":
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("focused_tests_not_reached",),
            )
        if "regression_tests" in required_checks and state != "regression_pass":
            return self._reject(
                session.plan.plan_id,
                True,
                tuple(results),
                ("regression_tests_not_reached",),
            )

        return VerificationReport(
            version="fap.repository.verification.v1",
            plan_id=session.plan.plan_id,
            state="verified_candidate",
            static_passed=True,
            commands=tuple(results),
            errors=(),
        )

    def _static_compile(
        self,
        session: SandboxSession,
        execution: ExecutionReport,
    ) -> CommandResult:
        started = time.monotonic()
        errors: list[str] = []
        checked: list[str] = []
        for item in execution.files:
            if item.operation == "delete" or not item.path.endswith(".py"):
                continue
            path = session.path / item.path
            checked.append(item.path)
            try:
                source = path.read_text(encoding="utf-8")
                compile(source, item.path, "exec")
            except Exception as exc:
                errors.append(f"{item.path}: {type(exc).__name__}: {exc}")
        elapsed = int((time.monotonic() - started) * 1000)
        output = "\n".join(errors)
        return CommandResult(
            name="python_static_compile",
            phase="static",
            argv=("<internal compile()>", *checked),
            returncode=0 if not errors else 1,
            duration_ms=elapsed,
            passed=not errors,
            timed_out=False,
            output_limited=False,
            output=output,
            error=None if not errors else "syntax_or_decode_error",
        )

    def _run_command(
        self,
        session: SandboxSession,
        command: VerificationCommand,
    ) -> CommandResult:
        env = self._minimal_env(session)
        started = time.monotonic()
        timed_out = False
        output_limited = False
        error: str | None = None
        returncode: int | None = None

        try:
            with tempfile.TemporaryFile() as sink:
                proc = subprocess.Popen(
                    list(command.argv),
                    cwd=session.path,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=sink,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
                deadline = started + command.timeout_sec
                while proc.poll() is None:
                    now = time.monotonic()
                    if now >= deadline:
                        timed_out = True
                        proc.kill()
                        break
                    if os.fstat(sink.fileno()).st_size > self.max_output_bytes:
                        output_limited = True
                        proc.kill()
                        break
                    time.sleep(self.poll_interval_sec)
                returncode = proc.wait(timeout=5)
                sink.seek(0)
                raw = sink.read(self.max_output_bytes + 1)
        except Exception as exc:
            raw = b""
            error = f"{type(exc).__name__}: {exc}"

        if len(raw) > self.max_output_bytes:
            raw = raw[: self.max_output_bytes]
            output_limited = True
        output = raw.decode("utf-8", errors="replace")
        if output_limited:
            output += "\n...<output limit reached>\n"
        if timed_out:
            output += "\n...<timeout>\n"
        elapsed = int((time.monotonic() - started) * 1000)
        passed = (
            error is None
            and not timed_out
            and not output_limited
            and returncode == 0
        )
        return CommandResult(
            name=command.name,
            phase=command.phase,
            argv=command.argv,
            returncode=returncode,
            duration_ms=elapsed,
            passed=passed,
            timed_out=timed_out,
            output_limited=output_limited,
            output=output,
            error=error,
        )

    def _validate_commands(
        self,
        commands: tuple[VerificationCommand, ...],
    ) -> None:
        if len(commands) > self.max_commands:
            raise ValueError("verification command limit exceeded")
        names: set[str] = set()
        for command in commands:
            if not command.name.strip():
                raise ValueError("verification command name is required")
            if command.name in names:
                raise ValueError(f"duplicate command name: {command.name}")
            names.add(command.name)
            if command.phase not in PHASES:
                raise ValueError(f"unsupported verification phase: {command.phase}")
            if not command.argv or len(command.argv) > 32:
                raise ValueError(f"invalid argv length: {command.name}")
            if not 1 <= int(command.timeout_sec) <= self.max_timeout_sec:
                raise ValueError(f"invalid timeout: {command.name}")
            executable = Path(command.argv[0]).name.casefold()
            if executable not in self.allowed_executables:
                raise ValueError(
                    f"executable not allowed for verification: {command.argv[0]}"
                )
            for arg in command.argv:
                if "\x00" in arg or len(arg) > 4096:
                    raise ValueError(f"invalid argv value: {command.name}")

    def _minimal_env(self, session: SandboxSession) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in (
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
            "LANG", "LC_ALL",
        ):
            if key in os.environ:
                env[key] = os.environ[key]
        for key in self.passthrough_env:
            if key in os.environ:
                env[key] = os.environ[key]

        home = session.temp_parent / "home"
        temp_dir = session.temp_parent / "tmp"
        home.mkdir(exist_ok=True)
        temp_dir.mkdir(exist_ok=True)
        env.update(
            {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "TMPDIR": str(temp_dir),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "NO_COLOR": "1",
                "CI": "1",
            }
        )
        return env

    def _sandbox_contamination(
        self,
        session: SandboxSession,
        execution: ExecutionReport,
    ) -> list[str]:
        expected = {item.path for item in execution.files}
        diff = session.executor._git(
            session.path,
            "diff", "--name-only", "--",
            timeout=session.executor.git_timeout_sec,
            check=False,
        )
        actual = {
            line.strip().replace("\\", "/")
            for line in diff.stdout.splitlines()
            if line.strip()
        }
        untracked = session.executor._git(
            session.path,
            "ls-files", "--others", "--exclude-standard",
            timeout=session.executor.git_timeout_sec,
            check=False,
        )
        extra_untracked = {
            line.strip().replace("\\", "/")
            for line in untracked.stdout.splitlines()
            if line.strip()
        }
        errors: list[str] = []
        unexpected = sorted(actual - expected)
        if unexpected:
            errors.append("unexpected_modified_paths:" + ",".join(unexpected))
        if extra_untracked:
            errors.append(
                "unexpected_untracked_paths:" + ",".join(sorted(extra_untracked))
            )
        return errors

    def _source_status(self, session: SandboxSession) -> str:
        proc = session.executor._git(
            session.executor.root,
            "status", "--porcelain", "--untracked-files=all",
            timeout=session.executor.git_timeout_sec,
            check=False,
        )
        return proc.stdout

    @staticmethod
    def _reject(
        plan_id: str,
        static_passed: bool,
        commands: tuple[CommandResult, ...],
        errors: tuple[str, ...],
    ) -> VerificationReport:
        return VerificationReport(
            version="fap.repository.verification.v1",
            plan_id=plan_id,
            state="rejected",
            static_passed=static_passed,
            commands=commands,
            errors=errors,
        )


class BoundedRepairLoop:
    """Retry a failing candidate with externally proposed edits, never unbounded."""

    def __init__(
        self,
        executor: RepositoryPatchExecutor,
        verifier: RepositoryVerifier,
        *,
        max_repairs: int = 2,
    ) -> None:
        if not 0 <= int(max_repairs) <= 4:
            raise ValueError("max_repairs must be in [0, 4]")
        self.executor = executor
        self.verifier = verifier
        self.max_repairs = int(max_repairs)

    def run(
        self,
        plan: PatchPlan,
        initial_edits: Iterable[FileEdit],
        commands: Iterable[VerificationCommand],
        *,
        repairer: RepairProvider | None = None,
    ) -> RepairRunReport:
        candidate = tuple(initial_edits)
        command_list = tuple(commands)
        attempts: list[CandidateAttempt] = []

        for round_index in range(self.max_repairs + 1):
            with self.executor.open(plan) as session:
                execution = session.apply(candidate)
                if execution.state == "applied_in_sandbox":
                    verification = self.verifier.verify(
                        session,
                        execution,
                        command_list,
                    )
                else:
                    verification = VerificationReport(
                        version="fap.repository.verification.v1",
                        plan_id=plan.plan_id,
                        state="rejected",
                        static_passed=False,
                        commands=(),
                        errors=("execution_rejected",) + tuple(execution.errors),
                    )
                attempt = CandidateAttempt(
                    round_index=round_index,
                    execution=execution,
                    verification=verification,
                )
                attempts.append(attempt)

            if verification.state == "verified_candidate":
                return RepairRunReport(
                    version="fap.repository.repair.v1",
                    plan_id=plan.plan_id,
                    state="verified_candidate",
                    repairs_used=round_index,
                    attempts=tuple(attempts),
                )

            if round_index >= self.max_repairs or repairer is None:
                break
            proposal = repairer(candidate, attempt)
            if proposal is None:
                break
            candidate = tuple(proposal)
            if not candidate:
                break

        errors = tuple(
            attempts[-1].verification.errors if attempts else ("no_attempts",)
        )
        return RepairRunReport(
            version="fap.repository.repair.v1",
            plan_id=plan.plan_id,
            state="rejected",
            repairs_used=max(0, len(attempts) - 1),
            attempts=tuple(attempts),
            errors=errors,
        )
