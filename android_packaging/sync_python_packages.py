from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any


_DEST_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PackagingError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackagingError("invalid package manifest") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise PackagingError("unsupported package manifest schema")
    packages = data.get("packages")
    if not isinstance(packages, list) or not packages:
        raise PackagingError("package manifest must contain packages")
    return data


def _safe_rel(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise PackagingError("package source must be a non-empty string")
    rel = PurePosixPath(value)
    if rel.is_absolute() or ".." in rel.parts or "." in rel.parts:
        raise PackagingError("package source must be a clean relative path")
    return rel


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise PackagingError(f"symlink source is forbidden: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PackagingError(f"symlink inside package is forbidden: {path}")


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_evidence(source: Path) -> dict[str, Any]:
    h = hashlib.sha256()
    count = 0
    size = 0
    files = [p for p in source.rglob("*") if p.is_file()]
    for path in sorted(files, key=lambda p: p.relative_to(source).as_posix()):
        rel = path.relative_to(source).as_posix()
        data_hash = _file_digest(path)
        n = path.stat().st_size
        count += 1
        size += n
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(data_hash.encode("ascii"))
        h.update(b"\0")
        h.update(str(n).encode("ascii"))
        h.update(b"\n")
    return {"tree_sha256": h.hexdigest(), "file_count": count, "bytes": size}


def _validate_packages(repo_root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    root = repo_root.resolve()
    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()
    validated: list[dict[str, Any]] = []

    for item in manifest["packages"]:
        if not isinstance(item, dict):
            raise PackagingError("package entry must be an object")
        source_value = item.get("source")
        destination = item.get("destination")
        rel = _safe_rel(source_value)
        if not isinstance(destination, str) or not _DEST_RE.fullmatch(destination):
            raise PackagingError("package destination must be a Python package identifier")
        source_key = rel.as_posix()
        if source_key in seen_sources:
            raise PackagingError("duplicate package source")
        if destination in seen_destinations:
            raise PackagingError("duplicate package destination")
        seen_sources.add(source_key)
        seen_destinations.add(destination)

        raw_source = repo_root.joinpath(*rel.parts)
        if raw_source.is_symlink():
            raise PackagingError("package source symlink is forbidden")
        if not raw_source.is_dir():
            raise PackagingError(f"package source missing: {source_key}")
        source = raw_source.resolve()
        if not source.is_relative_to(root):
            raise PackagingError("package source escapes repository root")
        _reject_symlinks(source)
        if not (source / "__init__.py").is_file():
            raise PackagingError(f"package missing __init__.py: {source_key}")

        evidence = _tree_evidence(source)
        validated.append({
            "source": source_key,
            "destination": destination,
            "source_path": source,
            **evidence,
        })
    return validated


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def sync_packages(
    *,
    repo_root: Path,
    destination_root: Path,
    manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    destination_root = destination_root.resolve()
    manifest = _load_manifest(manifest_path)
    validated = _validate_packages(repo_root, manifest)

    staging = Path(tempfile.mkdtemp(prefix=".fap_package_sync_", dir=str(destination_root)))
    try:
        for item in validated:
            shutil.copytree(
                item["source_path"],
                staging / item["destination"],
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )

        for item in validated:
            target = destination_root / item["destination"]
            if target.is_symlink():
                raise PackagingError("destination symlink is forbidden")
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            os.replace(staging / item["destination"], target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    manifest_for_digest = {
        "schema": manifest["schema"],
        "packages": [
            {"source": item["source"], "destination": item["destination"]}
            for item in validated
        ],
    }
    report = {
        "schema": 1,
        "manifest_sha256": hashlib.sha256(_canonical_json(manifest_for_digest)).hexdigest(),
        "packages": [
            {
                "source": item["source"],
                "destination": item["destination"],
                "tree_sha256": item["tree_sha256"],
                "file_count": item["file_count"],
                "bytes": item["bytes"],
            }
            for item in validated
        ],
    }
    _atomic_write(report_path, _canonical_json(report) + b"\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        report = sync_packages(
            repo_root=Path(args.repo_root),
            destination_root=Path(args.dest),
            manifest_path=Path(args.manifest),
            report_path=Path(args.report),
        )
    except PackagingError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
