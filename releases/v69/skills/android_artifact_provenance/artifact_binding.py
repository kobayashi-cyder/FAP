from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

_HEX = set("0123456789abcdef")


def _sha256_hex(value: str, field: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(c not in _HEX for c in text):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return text


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class AndroidArtifactBinding:
    schema: int
    package_name: str
    version_code: int
    version_name: str
    release: str
    source_commit: str
    artifact_sha256: str
    release_manifest_sha256: str
    verification_sha256: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def binding_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def build_binding(
    *,
    artifact_path: str,
    package_name: str,
    version_code: int,
    version_name: str,
    release: str,
    source_commit: str,
    release_manifest_sha256: str,
    verification_sha256: str,
) -> AndroidArtifactBinding:
    pkg = str(package_name).strip()
    rel = str(release).strip()
    commit = str(source_commit).strip().lower()
    if not pkg or not rel:
        raise ValueError("package_name and release are required")
    if int(version_code) < 1:
        raise ValueError("version_code must be >= 1")
    if len(commit) < 7 or any(c not in _HEX for c in commit):
        raise ValueError("source_commit must be a git hex SHA")
    return AndroidArtifactBinding(
        schema=1,
        package_name=pkg,
        version_code=int(version_code),
        version_name=str(version_name),
        release=rel,
        source_commit=commit,
        artifact_sha256=file_sha256(artifact_path),
        release_manifest_sha256=_sha256_hex(release_manifest_sha256, "release_manifest_sha256"),
        verification_sha256=_sha256_hex(verification_sha256, "verification_sha256"),
    )


def verify_binding(
    binding: AndroidArtifactBinding,
    *,
    artifact_path: str,
    expected_package: str | None = None,
    expected_version_code: int | None = None,
    expected_source_commit: str | None = None,
) -> dict[str, Any]:
    actual_artifact = file_sha256(artifact_path)
    if actual_artifact != binding.artifact_sha256:
        raise ValueError("artifact SHA-256 mismatch")
    if expected_package is not None and binding.package_name != str(expected_package):
        raise ValueError("package name mismatch")
    if expected_version_code is not None and binding.version_code != int(expected_version_code):
        raise ValueError("version code mismatch")
    if expected_source_commit is not None and binding.source_commit != str(expected_source_commit).lower():
        raise ValueError("source commit mismatch")
    return {
        "verified": True,
        "binding_sha256": binding.binding_sha256(),
        "artifact_sha256": actual_artifact,
        "release": binding.release,
        "source_commit": binding.source_commit,
    }


def binding_from_mapping(obj: Mapping[str, object]) -> AndroidArtifactBinding:
    if int(obj.get("schema", 0)) != 1:
        raise ValueError("unsupported artifact binding schema")
    return AndroidArtifactBinding(
        schema=1,
        package_name=str(obj.get("package_name", "")).strip(),
        version_code=int(obj.get("version_code", 0)),
        version_name=str(obj.get("version_name", "")),
        release=str(obj.get("release", "")).strip(),
        source_commit=str(obj.get("source_commit", "")).strip().lower(),
        artifact_sha256=_sha256_hex(str(obj.get("artifact_sha256", "")), "artifact_sha256"),
        release_manifest_sha256=_sha256_hex(str(obj.get("release_manifest_sha256", "")), "release_manifest_sha256"),
        verification_sha256=_sha256_hex(str(obj.get("verification_sha256", "")), "verification_sha256"),
    )
