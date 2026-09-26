#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATTERNS = (
    "tests/test_*.py",
    "android_packaging/tests/test_*.py",
    "candidates/**/tests/test_*.py",
    "releases/**/tests/test_*.py",
    "releases/**/test_*.py",
)


def discover(patterns: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(path)
    return sorted(out, key=lambda p: p.as_posix())


def pythonpath_for(test_file: Path) -> str:
    parent = test_file.parent
    entries: list[Path] = []

    # Put the test's own import root first so copied historical packages such as
    # fap_autonomy resolve to the matching release instead of another snapshot.
    if parent.name == "tests":
        entries.append(parent.parent)
    entries.append(parent)
    entries.append(ROOT)

    # Later V87 components intentionally build on earlier component packages.
    # Recreate that cumulative import surface without hard-coding a single test.
    releases = ROOT / "releases"
    if releases.exists():
        for release in sorted(releases.iterdir(), key=lambda p: p.name):
            if not release.is_dir():
                continue
            entries.append(release)
            for child in sorted(release.iterdir(), key=lambda p: p.name):
                if child.is_dir() and child.name not in {"tests", "examples"}:
                    entries.append(child)

    old = os.environ.get("PYTHONPATH", "")
    if old:
        entries.extend(Path(x) for x in old.split(os.pathsep) if x)
    unique: list[str] = []
    for entry in entries:
        value = str(entry)
        if value not in unique:
            unique.append(value)
    return os.pathsep.join(unique)


def run_one(path: Path, timeout: int) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath_for(path)
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.monotonic()
    try:
        cp = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                str(path),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.monotonic() - started
        return {
            "path": path.as_posix(),
            "state": "pass" if cp.returncode == 0 else "fail",
            "returncode": cp.returncode,
            "seconds": round(elapsed, 3),
            "stdout_tail": cp.stdout[-4000:],
            "stderr_tail": cp.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        return {
            "path": path.as_posix(),
            "state": "timeout",
            "returncode": None,
            "seconds": round(elapsed, 3),
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", default="runtime/test_sweep.json")
    parser.add_argument("--pattern", action="append", default=[])
    parser.add_argument("--max-tests", type=int, default=0)
    args = parser.parse_args()

    if not 5 <= args.timeout <= 600:
        raise SystemExit("--timeout must be in [5, 600]")

    patterns = tuple(args.pattern) if args.pattern else DEFAULT_PATTERNS
    tests = discover(patterns)
    if args.max_tests > 0:
        tests = tests[: args.max_tests]

    results: list[dict] = []
    for index, path in enumerate(tests, 1):
        result = run_one(path, args.timeout)
        results.append(result)
        print(
            f"[{index:03d}/{len(tests):03d}] "
            f"{result['state'].upper():7s} "
            f"{result['seconds']:7.3f}s {result['path']}",
            flush=True,
        )
        if result["state"] != "pass":
            tail = result["stderr_tail"] or result["stdout_tail"]
            if tail:
                print(tail[-2500:], flush=True)

    passed = sum(x["state"] == "pass" for x in results)
    failed = sum(x["state"] == "fail" for x in results)
    timed_out = sum(x["state"] == "timeout" for x in results)
    score = (passed / len(results) * 100.0) if results else 0.0
    report = {
        "contract": "fap.test-sweep.v1",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "timed_out": timed_out,
        "score_percent": round(score, 3),
        "results": results,
    }

    output = ROOT / args.json
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"SWEEP total={len(results)} pass={passed} fail={failed} "
        f"timeout={timed_out} score={score:.3f}%",
        flush=True,
    )
    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
