from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sys

from fap_repository_index import RepositoryIndexer
from fap_repository_planner import PatchPlan
from fap_repository_verifier import VerificationCommand


_SAFE_TEST_FILE = re.compile(r"^test[A-Za-z0-9_]*\.py$|^[A-Za-z0-9_]+_test\.py$")


@dataclass(frozen=True)
class VerificationSelection:
    version: str
    plan_id: str
    commands: tuple[VerificationCommand, ...]
    focused_tests: tuple[str, ...]
    regression_strategy: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryVerificationSelector:
    """Derive bounded Python verification commands from a Repository PatchPlan.

    Focused selection combines deterministic filename matching with bounded
    reverse import-dependency traversal. The selector never executes repository
    code and emits only explicit argv vectors for RepositoryVerifier.
    """

    VERSION = "fap.repository.verification_selector.v2"

    def __init__(
        self,
        root: str | Path,
        *,
        max_focused_tests: int = 6,
        timeout_sec: int = 60,
        dependency_hops: int = 2,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not 1 <= int(max_focused_tests) <= 16:
            raise ValueError("max_focused_tests must be in [1, 16]")
        if not 5 <= int(timeout_sec) <= 120:
            raise ValueError("timeout_sec must be in [5, 120]")
        if not 0 <= int(dependency_hops) <= 4:
            raise ValueError("dependency_hops must be in [0, 4]")
        self.max_focused_tests = int(max_focused_tests)
        self.timeout_sec = int(timeout_sec)
        self.dependency_hops = int(dependency_hops)

    def select(self, plan: PatchPlan) -> VerificationSelection:
        if plan.version != "fap.repository.plan.v1":
            raise ValueError(f"unsupported plan version: {plan.version}")

        required = set(plan.required_checks)
        mutated = tuple(
            item.path
            for item in plan.files
            if item.operation in {"modify", "create", "delete"}
        )
        python_targets = tuple(path for path in mutated if path.endswith(".py"))
        test_files = self._test_files()
        focused, selection_warnings = self._focused_tests(
            python_targets,
            test_files,
        )

        commands: list[VerificationCommand] = []
        warnings: list[str] = list(selection_warnings)

        if "focused_tests" in required:
            if focused:
                commands.append(
                    VerificationCommand(
                        name="auto_focused_unittest",
                        phase="focused",
                        argv=(
                            sys.executable,
                            "-m",
                            "unittest",
                            *(_module_name(path) for path in focused),
                            "-v",
                        ),
                        timeout_sec=self.timeout_sec,
                    )
                )
            elif test_files:
                commands.append(
                    VerificationCommand(
                        name="auto_focused_discover",
                        phase="focused",
                        argv=(
                            sys.executable,
                            "-m",
                            "unittest",
                            "discover",
                            "-s",
                            "tests",
                            "-v",
                        ),
                        timeout_sec=self.timeout_sec,
                    )
                )
                warnings.append("focused_test_mapping_fell_back_to_discovery")
            else:
                warnings.append("focused_tests_required_but_tests_directory_is_empty")

        regression_strategy = "not_required"
        if "regression_tests" in required:
            if test_files:
                commands.append(
                    VerificationCommand(
                        name="auto_regression_unittest",
                        phase="regression",
                        argv=(
                            sys.executable,
                            "-m",
                            "unittest",
                            "discover",
                            "-s",
                            "tests",
                            "-v",
                        ),
                        timeout_sec=self.timeout_sec,
                    )
                )
                regression_strategy = "unittest_discover"
            else:
                warnings.append("regression_tests_required_but_tests_directory_is_empty")
                regression_strategy = "unavailable"

        return VerificationSelection(
            version=self.VERSION,
            plan_id=plan.plan_id,
            commands=tuple(commands),
            focused_tests=focused,
            regression_strategy=regression_strategy,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _test_files(self) -> tuple[str, ...]:
        folder = self.root / "tests"
        if not folder.is_dir():
            return ()
        rows: list[str] = []
        for path in sorted(folder.rglob("*.py")):
            if path.is_symlink() or not path.is_file():
                continue
            if not _SAFE_TEST_FILE.fullmatch(path.name):
                continue
            rel = path.relative_to(self.root).as_posix()
            rows.append(rel)
        return tuple(rows)

    def _focused_tests(
        self,
        python_targets: tuple[str, ...],
        test_files: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not python_targets or not test_files:
            return (), ()

        selected: list[str] = []
        warnings: list[str] = []

        dependency_tests, dep_warnings = self._dependency_selected_tests(
            python_targets,
            test_files,
        )
        selected.extend(dependency_tests)
        warnings.extend(dep_warnings)

        stems = {
            Path(path).stem.casefold()
            for path in python_targets
            if not path.startswith("tests/")
        }
        direct_tests = {
            path
            for path in python_targets
            if path.startswith("tests/") and path in test_files
        }
        for path in test_files:
            if path in selected:
                continue
            if path in direct_tests:
                selected.append(path)
            else:
                name = Path(path).stem.casefold()
                if any(
                    name == f"test_{stem}"
                    or name == f"{stem}_test"
                    or name.startswith(f"test_{stem}_")
                    for stem in stems
                ):
                    selected.append(path)
            if len(selected) >= self.max_focused_tests:
                break

        return (
            tuple(dict.fromkeys(selected))[: self.max_focused_tests],
            tuple(dict.fromkeys(warnings)),
        )

    def _dependency_selected_tests(
        self,
        python_targets: tuple[str, ...],
        test_files: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if self.dependency_hops <= 0:
            return (), ()
        existing = tuple(
            path for path in python_targets
            if (self.root / path).is_file()
        )
        if not existing:
            return (), ()

        index = RepositoryIndexer(self.root).build()
        known = {row.path for row in index.files}
        seeds = tuple(path for path in existing if path in known)
        if not seeds:
            return (), ()

        reverse: dict[str, set[str]] = {}
        for edge in index.dependencies:
            reverse.setdefault(edge.target, set()).add(edge.source)

        queue = deque((path, 0) for path in seeds)
        seen = set(seeds)
        reachable_tests: list[str] = []
        test_set = set(test_files)

        while queue:
            current, distance = queue.popleft()
            if distance >= self.dependency_hops:
                continue
            for dependent in sorted(reverse.get(current, ())):
                if dependent in seen:
                    continue
                seen.add(dependent)
                if dependent in test_set:
                    reachable_tests.append(dependent)
                    if len(reachable_tests) >= self.max_focused_tests:
                        queue.clear()
                        break
                queue.append((dependent, distance + 1))

        warnings: list[str] = []
        if index.errors:
            warnings.append("repository_index_contains_errors")
        return tuple(dict.fromkeys(reachable_tests)), tuple(warnings)


def _module_name(path: str) -> str:
    value = str(path).replace("\\", "/")
    if not value.endswith(".py"):
        raise ValueError("test module path must end in .py")
    return value[:-3].replace("/", ".")
