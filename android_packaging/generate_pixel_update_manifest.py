from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

try:
    from .sync_pixel_runtime import DEFAULT_SEEDS, dependency_closure
except ImportError:
    from sync_pixel_runtime import DEFAULT_SEEDS, dependency_closure


SHA40 = re.compile(r"^[0-9a-f]{40}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(repo_root: Path, source_commit: str) -> dict:
    root = repo_root.resolve()
    commit = source_commit.strip().lower()
    if not SHA40.fullmatch(commit):
        raise ValueError("source_commit must be a full 40-character lowercase Git SHA")

    files = []
    for path in dependency_closure(root, DEFAULT_SEEDS):
        files.append(
            {
                "path": path.name,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    knowledge_root = root / "knowledge"
    if knowledge_root.is_dir():
        for path in sorted(knowledge_root.rglob("*.jsonl")):
            rel = path.relative_to(root).as_posix()
            files.append(
                {
                    "path": rel,
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )

    files.sort(key=lambda row: row["path"])
    return {
        "schema": "fap.pixel.runtime.manifest.v1",
        "runtime_version": "1.0.01",
        "source_commit": commit,
        "entrypoint": "fap_1x_standard_runtime.py",
        "file_count": len(files),
        "total_bytes": sum(int(row["bytes"]) for row in files),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the immutable full-file manifest consumed by Pixel Git OTA."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = generate(Path(args.repo_root), args.source_commit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
