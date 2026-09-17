from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class CompactionRecord:
    evidence_id: str
    capability_id: str
    created_at: float
    payload: Mapping[str, object]


@dataclass(frozen=True)
class CompactionManifest:
    format: str
    sha256: str
    count: int
    raw_bytes: int
    compressed_bytes: int
    evidence_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_line(record: CompactionRecord) -> bytes:
    if not str(record.evidence_id).strip() or not str(record.capability_id).strip():
        raise ValueError("evidence_id and capability_id are required")
    obj = {
        "evidence_id": str(record.evidence_id),
        "capability_id": str(record.capability_id),
        "created_at": float(record.created_at),
        "payload": dict(record.payload),
    }
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def build_segment(records: Iterable[CompactionRecord]) -> tuple[bytes, CompactionManifest]:
    rows = list(records)
    rows.sort(key=lambda r: (str(r.capability_id), float(r.created_at), str(r.evidence_id)))
    ids = [str(r.evidence_id) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate evidence_id in compaction segment")
    raw = b"".join(_canonical_line(r) for r in rows)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    manifest = CompactionManifest(
        format="fap-evidence-jsonl-gzip-v1",
        sha256=hashlib.sha256(compressed).hexdigest(),
        count=len(rows),
        raw_bytes=len(raw),
        compressed_bytes=len(compressed),
        evidence_ids=tuple(ids),
    )
    return compressed, manifest


def verify_segment(blob: bytes, manifest: CompactionManifest) -> tuple[dict[str, object], ...]:
    if manifest.format != "fap-evidence-jsonl-gzip-v1":
        raise ValueError("unsupported compaction format")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != manifest.sha256:
        raise ValueError("compaction digest mismatch")
    try:
        raw = gzip.decompress(blob)
    except OSError as exc:
        raise ValueError("invalid gzip compaction segment") from exc
    if len(raw) != manifest.raw_bytes or len(blob) != manifest.compressed_bytes:
        raise ValueError("compaction size mismatch")
    parsed = []
    for line in raw.splitlines():
        if not line:
            continue
        obj = json.loads(line.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("compaction row must be an object")
        parsed.append(obj)
    ids = tuple(str(x.get("evidence_id", "")) for x in parsed)
    if len(parsed) != manifest.count or ids != manifest.evidence_ids:
        raise ValueError("compaction manifest contents mismatch")
    return tuple(parsed)


def atomic_write_segment(path: str, blob: bytes, manifest: CompactionManifest) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    verify_segment(blob, manifest)
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
