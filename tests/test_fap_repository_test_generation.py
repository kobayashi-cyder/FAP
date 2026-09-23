from __future__ import annotations

from pathlib import Path
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

    def test_raises_case_is_generated(self) -> None:
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

    def test_unsupported_literal_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "unsupported literal type"):
            RepositoryPythonTestGenerator().generate(
                PythonUnitTestSpec(
                    module="calc",
                    function="add",
                    cases=(PythonExampleCase("bad", args=(object(),), expected=1),),
                )
            )


if __name__ == "__main__":
    unittest.main()
