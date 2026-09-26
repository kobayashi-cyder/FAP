from __future__ import annotations

from dataclasses import dataclass
import ast
import builtins
import math
import re
from typing import Any, Mapping


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass(frozen=True)
class PythonExampleCase:
    name: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] | None = None
    expected: Any = None
    raises: str | None = None


@dataclass(frozen=True)
class PythonUnitTestSpec:
    module: str
    function: str
    cases: tuple[PythonExampleCase, ...]
    class_name: str = "GeneratedTests"


class RepositoryPythonTestGenerator:
    """Generate bounded, reviewable unittest source from explicit examples."""

    VERSION = "fap.repository.test_generation.v1"

    def __init__(
        self,
        *,
        max_cases: int = 128,
        max_source_chars: int = 100_000,
    ) -> None:
        if not 1 <= int(max_cases) <= 1024:
            raise ValueError("max_cases must be in [1, 1024]")
        if not 1_000 <= int(max_source_chars) <= 1_000_000:
            raise ValueError("max_source_chars must be in [1000, 1000000]")
        self.max_cases = int(max_cases)
        self.max_source_chars = int(max_source_chars)

    def generate(self, spec: PythonUnitTestSpec) -> str:
        if not _SAFE_MODULE.fullmatch(spec.module):
            raise ValueError("module must be a safe dotted Python module")
        if not _SAFE_NAME.fullmatch(spec.function):
            raise ValueError("function must be a safe Python identifier")
        if not _SAFE_NAME.fullmatch(spec.class_name):
            raise ValueError("class_name must be a safe Python identifier")
        if not spec.cases:
            raise ValueError("at least one example case is required")
        if len(spec.cases) > self.max_cases:
            raise ValueError("example case limit exceeded")

        methods: list[str] = []
        seen: set[str] = set()
        for index, case in enumerate(spec.cases):
            method = _test_method(case.name, index)
            if method in seen:
                raise ValueError(f"duplicate generated test name: {method}")
            seen.add(method)
            call = _render_call(spec.function, case.args, case.kwargs or {})
            if case.raises is not None:
                exception_name = _exception_name(case.raises)
                body = (
                    f"        with self.assertRaises({exception_name}):\n"
                    f"            {call}\n"
                )
            else:
                expected = _literal(case.expected)
                body = (
                    f"        actual = {call}\n"
                    f"        self.assertEqual(actual, {expected})\n"
                )
            methods.append(f"    def {method}(self):\n{body}")

        source = (
            "from __future__ import annotations\n\n"
            "import unittest\n"
            f"from {spec.module} import {spec.function}\n\n\n"
            f"class {spec.class_name}(unittest.TestCase):\n"
            + "\n".join(methods)
            + "\n\n\nif __name__ == \"__main__\":\n"
            "    unittest.main()\n"
        )
        if len(source) > self.max_source_chars:
            raise ValueError("generated test source limit exceeded")

        tree = ast.parse(source, filename="<generated-test>")
        compile(tree, "<generated-test>", "exec")
        return source


def _test_method(raw: str, index: int) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "")).strip("_").lower()
    if not value:
        value = f"case_{index}"
    if value[0].isdigit():
        value = "case_" + value
    return "test_" + value


def _render_call(
    function: str,
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
) -> str:
    parts = [_literal(value) for value in args]
    keys = tuple(kwargs.keys())
    if any(not isinstance(key, str) for key in keys):
        raise ValueError("keyword names must be strings")
    for key in sorted(keys):
        if not _SAFE_NAME.fullmatch(key):
            raise ValueError("keyword names must be safe Python identifiers")
        parts.append(f"{key}={_literal(kwargs[key])}")
    return f"{function}({', '.join(parts)})"


def _exception_name(raw: str) -> str:
    name = str(raw or "").strip()
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError("raises must name a built-in Exception type")
    candidate = getattr(builtins, name, None)
    if (
        not isinstance(candidate, type)
        or not issubclass(candidate, Exception)
    ):
        raise ValueError("raises must name a built-in Exception type")
    return name


def _literal(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, str, bytes)):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not supported")
        return repr(value)
    if isinstance(value, tuple):
        body = ", ".join(_literal(x) for x in value)
        if len(value) == 1:
            body += ","
        return f"({body})"
    if isinstance(value, list):
        return "[" + ", ".join(_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        rows = []
        for key in sorted(value, key=lambda x: repr(x)):
            rows.append(f"{_literal(key)}: {_literal(value[key])}")
        return "{" + ", ".join(rows) + "}"
    raise TypeError(f"unsupported literal type: {type(value).__name__}")
