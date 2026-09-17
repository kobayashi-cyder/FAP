from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class StaticSafetyGate:
    """Conservative gate for generated Python skill candidates.

    This is not a security boundary. It is a pre-sandbox rejection layer.
    The candidate must still execute in an OS/container sandbox in production.
    """

    BANNED_IMPORT_ROOTS = {
        "socket", "requests", "urllib", "http", "ftplib", "telnetlib",
        "subprocess", "multiprocessing", "ctypes", "winreg", "paramiko",
    }
    BANNED_CALLS = {
        "eval", "exec", "compile", "__import__", "breakpoint",
        "os.system", "os.popen", "os.remove", "os.unlink", "os.rmdir", "os.removedirs",
        "shutil.rmtree",
    }

    def inspect_source(self, source: str, filename: str = "<candidate>") -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            return {"safe": False, "issues": [{"type": "syntax", "line": e.lineno, "message": str(e)}]}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in self.BANNED_IMPORT_ROOTS:
                        issues.append({"type": "import", "line": node.lineno, "name": alias.name})
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".", 1)[0]
                if root in self.BANNED_IMPORT_ROOTS:
                    issues.append({"type": "import", "line": node.lineno, "name": node.module})
            elif isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name in self.BANNED_CALLS:
                    issues.append({"type": "call", "line": getattr(node, "lineno", None), "name": name})
            elif isinstance(node, ast.Attribute) and node.attr in {"__subclasses__", "__globals__", "__code__"}:
                issues.append({"type": "introspection", "line": getattr(node, "lineno", None), "name": node.attr})
        return {"safe": not issues, "issues": issues}

    def inspect_tree(self, path: str) -> Dict[str, Any]:
        root = Path(path)
        issues = []
        checked = 0
        for p in root.rglob("*.py"):
            if any(part.startswith(".") or part == "__pycache__" for part in p.parts):
                continue
            checked += 1
            r = self.inspect_source(p.read_text(encoding="utf-8"), str(p))
            for issue in r["issues"]:
                issue = dict(issue)
                issue["file"] = str(p.relative_to(root))
                issues.append(issue)
        return {"safe": not issues, "issues": issues, "files_checked": checked}

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = StaticSafetyGate._call_name(node.value)
            return f"{left}.{node.attr}" if left else node.attr
        return ""


class SubprocessTestSandbox:
    """Small execution wrapper for tests. Production should replace this with the existing FAP sandbox."""

    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds

    def run(self, candidate_dir: str, command: Optional[List[str]] = None) -> Dict[str, Any]:
        cmd = command or [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
        env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
        }
        t0 = time.perf_counter()
        try:
            cp = subprocess.run(
                cmd, cwd=candidate_dir, capture_output=True, text=True,
                timeout=self.timeout_seconds, env=env,
            )
            elapsed = time.perf_counter() - t0
            return {
                "pass": cp.returncode == 0,
                "returncode": cp.returncode,
                "stdout": cp.stdout[-12000:],
                "stderr": cp.stderr[-12000:],
                "test_seconds": elapsed,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "pass": False, "returncode": None,
                "stdout": (e.stdout or "")[-12000:] if isinstance(e.stdout, str) else "",
                "stderr": "timeout", "test_seconds": self.timeout_seconds,
            }


class SafeCandidateVerifier:
    """Static gate + unit test + sandbox evidence aggregator.

    Artifact contract:
      {"candidate_dir": "...", "test_command": [...], "ram_mb": measured_ram_or_None}

    RAM must come from the target FAP sandbox/resource monitor. If absent, resource completeness is false,
    which intentionally prevents a claim of full Definition-of-Done.
    """

    def __init__(self, timeout_seconds: float = 30.0):
        self.gate = StaticSafetyGate()
        self.sandbox = SubprocessTestSandbox(timeout_seconds)

    def verify(self, artifact: Dict[str, Any], *, capability_id: str) -> Dict[str, Any]:
        candidate_dir = artifact["candidate_dir"]
        static = self.gate.inspect_tree(candidate_dir)
        if not static["safe"]:
            return {
                "static_safe": False, "unit_pass": False, "sandbox_pass": False,
                "verified_success": False, "confidence": 0.0,
                "static": static,
                "resources": self._resources(candidate_dir, 0.0, artifact.get("ram_mb")),
            }
        test = self.sandbox.run(candidate_dir, artifact.get("test_command"))
        resources = self._resources(candidate_dir, test["test_seconds"], artifact.get("ram_mb"))
        complete = artifact.get("ram_mb") is not None
        passed = bool(test["pass"])
        return {
            "static_safe": True,
            "unit_pass": passed,
            "sandbox_pass": passed,
            "verified_success": passed,
            "confidence": 0.80 if passed and complete else (0.70 if passed else 0.0),
            "static": static,
            "test": test,
            "resources": resources,
            "resource_measurement_complete": complete,
        }

    @staticmethod
    def _resources(candidate_dir: str, test_seconds: float, ram_mb: Optional[float]) -> Dict[str, Any]:
        root = Path(candidate_dir)
        code_bytes = sum(p.stat().st_size for p in root.rglob("*.py") if p.is_file())
        disk_bytes = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        return {
            "code_kb": code_bytes / 1024.0,
            "disk_mb": disk_bytes / (1024.0 * 1024.0),
            "ram_mb": ram_mb,
            "test_seconds": test_seconds,
        }
