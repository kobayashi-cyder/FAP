from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re

from fap_repository_planner import PatchPlan


_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_MUTATIONS = frozenset({"modify", "create", "delete"})
_OPERATIONS = frozenset({"inspect", *_MUTATIONS})


@dataclass(frozen=True)
class PlanQualityIssue:
    code: str
    severity: str
    path: str = ""


@dataclass(frozen=True)
class PlanQualityReport:
    version: str
    plan_id: str
    acceptable: bool
    mutation_count: int
    inspect_count: int
    issues: tuple[PlanQualityIssue, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryPlanQualityGate:
    """Fail-closed execution-quality gate over a produced PatchPlan."""

    VERSION = "fap.repository.plan_quality.v1"

    def __init__(
        self,
        *,
        max_files: int = 8,
        require_mutation: bool = True,
    ) -> None:
        if not 1 <= int(max_files) <= 64:
            raise ValueError("max_files must be in [1, 64]")
        self.max_files = int(max_files)
        self.require_mutation = bool(require_mutation)

    def assess(self, plan: PatchPlan) -> PlanQualityReport:
        issues: list[PlanQualityIssue] = []
        seen: set[str] = set()
        mutations = 0
        inspections = 0
        python_mutation = False

        if plan.version != "fap.repository.plan.v1":
            issues.append(PlanQualityIssue("unsupported_plan_version", "fatal"))
        if not _HEX64.fullmatch(str(plan.plan_id or "")):
            issues.append(PlanQualityIssue("invalid_plan_id", "fatal"))
        if plan.status != "ready":
            issues.append(PlanQualityIssue("plan_not_ready", "fatal"))
        if plan.write_enabled:
            issues.append(PlanQualityIssue("plan_write_enabled", "fatal"))
        if len(plan.files) > self.max_files:
            issues.append(PlanQualityIssue("plan_file_limit_exceeded", "fatal"))

        for item in plan.files:
            path = _safe_path(item.path)
            if path is None:
                issues.append(
                    PlanQualityIssue("unsafe_plan_path", "fatal", str(item.path))
                )
                continue
            if path in seen:
                issues.append(PlanQualityIssue("duplicate_path", "fatal", path))
            seen.add(path)

            if item.operation not in _OPERATIONS:
                issues.append(
                    PlanQualityIssue("unsupported_operation", "fatal", path)
                )
                continue

            if item.operation == "inspect":
                inspections += 1
                continue

            mutations += 1
            python_mutation = python_mutation or path.endswith(".py")
            if item.operation == "create":
                if item.before_sha256:
                    issues.append(
                        PlanQualityIssue(
                            "create_has_before_hash",
                            "fatal",
                            path,
                        )
                    )
            elif not _HEX64.fullmatch(str(item.before_sha256 or "")):
                issues.append(
                    PlanQualityIssue(
                        "mutation_invalid_before_hash",
                        "fatal",
                        path,
                    )
                )

        checks = set(plan.required_checks)
        if mutations:
            for check, code in (
                ("sha_precondition", "missing_sha_precondition"),
                ("sandbox_only", "missing_sandbox_only"),
                ("no_direct_main_write", "missing_no_direct_main_write"),
                ("regression_tests", "missing_regression_tests"),
            ):
                if check not in checks:
                    issues.append(PlanQualityIssue(code, "fatal"))
            if python_mutation:
                if "python_compile" not in checks:
                    issues.append(
                        PlanQualityIssue("missing_python_compile", "fatal")
                    )
                if "focused_tests" not in checks:
                    issues.append(
                        PlanQualityIssue("missing_focused_tests", "fatal")
                    )
        elif self.require_mutation:
            issues.append(PlanQualityIssue("no_mutation_targets", "fatal"))
        else:
            issues.append(PlanQualityIssue("no_mutation_targets", "warning"))

        if len(plan.files) > 4:
            issues.append(PlanQualityIssue("broad_plan", "warning"))
        if "stale_context" in plan.risk_flags:
            issues.append(PlanQualityIssue("stale_context_risk", "fatal"))

        acceptable = not any(issue.severity == "fatal" for issue in issues)
        return PlanQualityReport(
            version=self.VERSION,
            plan_id=plan.plan_id,
            acceptable=acceptable,
            mutation_count=mutations,
            inspect_count=inspections,
            issues=tuple(issues),
        )


def _safe_path(raw: object) -> str | None:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or "\x00" in value
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
    ):
        return None
    return posix.as_posix()
