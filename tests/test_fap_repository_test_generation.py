from __future__ import annotations

from pathlib import Path
import math
import subprocess
import sys
import tempfile
import unittest

from fap_repository_test_generation import (
    PythonExampleCase,
    PythonUnitTestSpec,
    RepositoryPythonTestGenerator,
)


class RepositoryPythonTestGeneratorTests(unittest.TestCase):
    def test_generated_unittest_compiles_and_runs(self) -> None:
        source = RepositoryPythonTestGenerator().generate(
            PythonUnitTestSpec(
                module="calc",
                function="add",
                cases=(
                    PythonExampleCase("integers", args=(2, 3), expected=5),
                    PythonExampleCase("negative", args=(-1, 1), expected=0),
                ),
            )
        )
        compile(source, "<test>", "exec")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "calc.py").write_text(
                "def add(a, b):\n    return a + b\n",
                encoding="utf-8",
            )
            (root / "test_generated.py").write_text(source, encoding="utf-8")
            cp = subprocess.run(
                [sys.executable, "-m", "unittest", "test_generated", "-v"],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout)

    def test_raises_case_is_generated_for_builtin_exception(self) -> None:
        source = RepositoryPythonTestGenerator().generate(
            PythonUnitTestSpec(
                module="calc",
                function="divide",
                cases=(
                    PythonExampleCase(
                        "zero",
                        args=(1, 0),
                        raises="ZeroDivisionError",
                    ),
                ),
            )
        )
        self.assertIn("with self.assertRaises(ZeroDivisionError)", source)

    def test_non_exception_raises_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "built-in Exception"):
            RepositoryPythonTestGenerator().generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="divide",
                    cases=(
                        PythonExampleCase(
                            "bad",
                            args=(1, 0),
                            raises="SystemExit",
                        ),
                    ),
                )
            )

    def test_non_finite_float_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-finite"):
            RepositoryPythonTestGenerator().generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="identity",
                    cases=(
                        PythonExampleCase(
                            "nan",
                            args=(math.nan,),
                            expected=math.nan,
                        ),
                    ),
                )
            )

    def test_case_and_source_limits_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "case limit"):
            RepositoryPythonTestGenerator(max_cases=1).generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="add",
                    cases=(
                        PythonExampleCase("a", args=(1, 1), expected=2),
                        PythonExampleCase("b", args=(2, 2), expected=4),
                    ),
                )
            )

        generator = RepositoryPythonTestGenerator(max_source_chars=1000)
        huge = "x" * 950
        with self.assertRaisesRegex(ValueError, "source limit"):
            generator.generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="identity",
                    cases=(
                        PythonExampleCase("huge", args=(huge,), expected=huge),
                    ),
                )
            )

    def test_unsupported_literal_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "unsupported literal type"):
            RepositoryPythonTestGenerator().generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="add",
                    cases=(
                        PythonExampleCase(
                            "bad",
                            args=(object(),),
                            expected=1,
                        ),
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
