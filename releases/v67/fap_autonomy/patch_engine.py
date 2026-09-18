from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional


class PatchError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise PatchError('path escapes workspace')
    return p


@dataclass(frozen=True)
class FilePatch:
    path: str
    content: str
    base_sha256: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PatchSet:
    reason: str
    patches: tuple[FilePatch, ...]

    def digest(self) -> str:
        raw = json.dumps({'reason': self.reason, 'patches': [p.to_dict() for p in self.patches]},
                         ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()


class RepositoryPatchApplier:
    def __init__(self, workspace: str, *, max_patch_bytes: int = 256_000):
        self.root = Path(workspace).resolve()
        self.max_patch_bytes = int(max_patch_bytes)
        if not self.root.is_dir() or self.root.is_symlink():
            raise PatchError('invalid workspace')

    def apply(self, patch_set: PatchSet) -> dict:
        total = sum(len(p.content.encode('utf-8')) for p in patch_set.patches)
        if total > self.max_patch_bytes:
            raise PatchError('patch budget exceeded')
        staged: List[tuple[Path, bytes]] = []
        for p in patch_set.patches:
            dest = _safe(self.root, p.path)
            if dest.exists() and dest.is_symlink():
                raise PatchError('symlink target rejected')
            if any(parent.is_symlink() for parent in dest.parents if parent != self.root.parent):
                raise PatchError('symlink parent rejected')
            current = dest.read_bytes() if dest.exists() else None
            if p.base_sha256 is not None:
                if current is None or sha256_bytes(current) != p.base_sha256:
                    raise PatchError(f'base hash mismatch: {p.path}')
            staged.append((dest, p.content.encode('utf-8')))
        changed = []
        for dest, raw in staged:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            changed.append(dest.relative_to(self.root).as_posix())
        return {'patch_digest': patch_set.digest(), 'changed_files': changed, 'bytes': total}
