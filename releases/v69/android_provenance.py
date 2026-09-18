from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

_HEX = frozenset("0123456789abcdef")


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_sha(value: str) -> str:
    value = str(value).strip().lower()
    if len(value) != 40 or any(c not in _HEX for c in value):
        raise ValueError("source_sha must be a full 40-character git SHA")
    return value


@dataclass(frozen=True)
class PackageMetadata:
    package_name: str
    version_code: int
    version_name: str


@dataclass(frozen=True)
class AndroidProvenance:
    schema: int
    package_name: str
    version_code: int
    version_name: str
    source_sha: str
    release_id: str
    artifact_sha256: str
    release_manifest_sha256: str | None
    verification_summary_sha256: str | None

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def digest(self) -> str:
        return _sha256_bytes(self.canonical_bytes())


def _validate_metadata(metadata: PackageMetadata) -> None:
    if not metadata.package_name.strip():
        raise ValueError("package_name is required")
    if metadata.version_code < 1:
        raise ValueError("version_code must be >= 1")
    if not metadata.version_name.strip():
        raise ValueError("version_name is required")


def build_provenance(
    artifact_path: str | Path,
    package_metadata: PackageMetadata,
    source_sha: str,
    release_id: str,
    release_manifest: bytes | None = None,
    verification_summary: bytes | None = None,
) -> AndroidProvenance:
    _validate_metadata(package_metadata)
    if not str(release_id).strip():
        raise ValueError("release_id is required")
    return AndroidProvenance(
        schema=1,
        package_name=package_metadata.package_name.strip(),
        version_code=package_metadata.version_code,
        version_name=package_metadata.version_name.strip(),
        source_sha=_git_sha(source_sha),
        release_id=str(release_id).strip(),
        artifact_sha256=_sha256_file(artifact_path),
        release_manifest_sha256=None if release_manifest is None else _sha256_bytes(release_manifest),
        verification_summary_sha256=None if verification_summary is None else _sha256_bytes(verification_summary),
    )


def from_mapping(obj: Mapping[str, object]) -> AndroidProvenance:
    allowed = {"schema", "package_name", "version_code", "version_name", "source_sha", "release_id", "artifact_sha256", "release_manifest_sha256", "verification_summary_sha256"}
    if set(obj) != allowed:
        raise ValueError("malformed or duplicate/conflicting provenance fields")
    if obj.get("schema") != 1:
        raise ValueError("unsupported provenance schema")
    metadata = PackageMetadata(str(obj["package_name"]), int(obj["version_code"]), str(obj["version_name"]))
    _validate_metadata(metadata)
    artifact_hash = str(obj["artifact_sha256"]).lower()
    if len(artifact_hash) != 64 or any(c not in _HEX for c in artifact_hash):
        raise ValueError("malformed artifact hash")
    def optional_hash(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).lower()
        if len(text) != 64 or any(c not in _HEX for c in text):
            raise ValueError("malformed optional hash")
        return text
    return AndroidProvenance(1, metadata.package_name.strip(), metadata.version_code, metadata.version_name.strip(), _git_sha(str(obj["source_sha"])), str(obj["release_id"]).strip(), artifact_hash, optional_hash(obj["release_manifest_sha256"]), optional_hash(obj["verification_summary_sha256"]))


def verify_provenance(
    record: AndroidProvenance,
    artifact_path: str | Path,
    expected_package: PackageMetadata | None = None,
    expected_source_sha: str | None = None,
    release_manifest: bytes | None = None,
    verification_summary: bytes | None = None,
) -> bool:
    if _sha256_file(artifact_path) != record.artifact_sha256:
        raise ValueError("artifact SHA-256 mismatch")
    if expected_package is not None:
        _validate_metadata(expected_package)
        if (record.package_name, record.version_code, record.version_name) != (expected_package.package_name.strip(), expected_package.version_code, expected_package.version_name.strip()):
            raise ValueError("package metadata mismatch")
    if expected_source_sha is not None and record.source_sha != _git_sha(expected_source_sha):
        raise ValueError("source SHA mismatch")
    if record.release_manifest_sha256 is not None:
        if release_manifest is None or _sha256_bytes(release_manifest) != record.release_manifest_sha256:
            raise ValueError("release manifest mismatch")
    elif release_manifest is not None:
        raise ValueError("unexpected release manifest")
    if record.verification_summary_sha256 is not None:
        if verification_summary is None or _sha256_bytes(verification_summary) != record.verification_summary_sha256:
            raise ValueError("verification summary mismatch")
    elif verification_summary is not None:
        raise ValueError("unexpected verification summary")
    return True
