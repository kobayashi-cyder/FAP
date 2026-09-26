from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
from typing import Iterable


DEFAULT_SEEDS = ("fap_1x_standard_runtime.py",)


def local_fap_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root.startswith("fap_"):
                    names.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = (node.module or "").split(".", 1)[0]
            if module.startswith("fap_"):
                names.add(module)
    return tuple(sorted(names))


def dependency_closure(repo_root: Path, seeds: Iterable[str]) -> tuple[Path, ...]:
    root = repo_root.resolve()
    pending = [str(seed) for seed in seeds]
    found: dict[str, Path] = {}

    while pending:
        rel = pending.pop(0)
        if rel in found:
            continue
        path = (root / rel).resolve()
        if path.parent != root or not path.is_file():
            raise FileNotFoundError(f"required Pixel runtime module missing: {rel}")
        found[rel] = path

        for module in local_fap_imports(path):
            dep = f"{module}.py"
            if dep not in found and dep not in pending:
                candidate = root / dep
                if candidate.is_file():
                    pending.append(dep)

    return tuple(found[key] for key in sorted(found))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync(
    repo_root: Path,
    dest: Path,
    *,
    seeds: Iterable[str] = DEFAULT_SEEDS,
    report: Path | None = None,
) -> dict:
    repo_root = repo_root.resolve()
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    # Remove only generated FAP modules from previous packaging runs. Keep the
    # Android-owned bridge and build metadata under app/src/main/python.
    for path in dest.glob("fap_*.py"):
        path.unlink()
    knowledge_dest = dest / "knowledge"
    if knowledge_dest.exists():
        shutil.rmtree(knowledge_dest)

    modules = dependency_closure(repo_root, seeds)
    rows = []
    for source in modules:
        target = dest / source.name
        shutil.copy2(source, target)
        rows.append(
            {
                "path": source.name,
                "sha256": sha256(source),
                "bytes": source.stat().st_size,
            }
        )

    knowledge_source = repo_root / "knowledge"
    knowledge_files = []
    if knowledge_source.is_dir():
        for source in sorted(knowledge_source.rglob("*.jsonl")):
            rel = source.relative_to(knowledge_source)
            target = knowledge_dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            knowledge_files.append(
                {
                    "path": f"knowledge/{rel.as_posix()}",
                    "sha256": sha256(source),
                    "bytes": source.stat().st_size,
                }
            )

    payload = {
        "version": "fap.pixel.package.v1",
        "seeds": list(seeds),
        "module_count": len(rows),
        "knowledge_file_count": len(knowledge_files),
        "modules": rows,
        "knowledge": knowledge_files,
        "total_bytes": sum(row["bytes"] for row in rows + knowledge_files),
    }

    if report is not None:
        report = report.resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy the minimal current FAP 1.x dependency closure into the Pixel APK."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--seed", action="append", default=[])
    args = parser.parse_args()

    payload = sync(
        Path(args.repo_root),
        Path(args.dest),
        seeds=tuple(args.seed) or DEFAULT_SEEDS,
        report=Path(args.report) if args.report else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
