from __future__ import annotations

from pathlib import Path
from typing import Optional

from .responder import (
    LearningArtifactError,
    TeacherLearningState,
    _canonical_json_digest,
)


# Trust anchor for the reviewed V78 provenance manifest. The manifest contains
# hashes for the learned-state files, so anchoring it prevents an attacker from
# changing both a learned-state file and its expected hash in one edit.
V78_PROVENANCE_CANONICAL_SHA256 = (
    "50de0f22d3a30cb992e5399a70d60126cf97a51ab9e826adc96413b14025fceb"
)


class TrustedTeacherLearningState(TeacherLearningState):
    """V78 loader that anchors the provenance manifest before trusting its hashes."""

    def __init__(self, data_dir: Optional[Path | str] = None):
        resolved = Path(data_dir) if data_dir is not None else Path(__file__).with_name("data")
        manifest = resolved / "provenance.json"
        digest = _canonical_json_digest(manifest)
        if digest != V78_PROVENANCE_CANONICAL_SHA256:
            raise LearningArtifactError("learning provenance digest mismatch")
        super().__init__(resolved, verify_integrity=True)
