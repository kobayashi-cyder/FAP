from __future__ import annotations

import re
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Dict

from .quarantine import QuarantineLedger

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceQuarantineLedger(QuarantineLedger):
    """Quarantine ledger that can only be released by fresh verified untouched holdout evidence."""

    def __init__(self, path: str, *, candidate_threshold: int = 3, family_threshold: int = 5,
                 min_holdout_score: float = 0.5, max_regression: float = 0.02):
        super().__init__(path, candidate_threshold=candidate_threshold, family_threshold=family_threshold)
        self.min_holdout_score = float(min_holdout_score)
        self.max_regression = float(max_regression)
        with closing(sqlite3.connect(self.path)) as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS releases(
                       release_id TEXT PRIMARY KEY,
                       capability_id TEXT NOT NULL,
                       candidate_digest TEXT NOT NULL,
                       family TEXT NOT NULL,
                       scope TEXT NOT NULL,
                       evidence_sha256 TEXT NOT NULL UNIQUE,
                       holdout_score REAL NOT NULL,
                       baseline_score REAL NOT NULL,
                       created_at REAL NOT NULL
                   )"""
            )

    def _last_release(self, *, capability_id: str, candidate_digest: str, family: str, scope: str) -> float:
        with closing(sqlite3.connect(self.path)) as con:
            if scope == "candidate":
                row = con.execute("SELECT MAX(created_at) FROM releases WHERE capability_id=? AND candidate_digest=? AND scope='candidate'",
                                  (capability_id, candidate_digest)).fetchone()
            else:
                row = con.execute("SELECT MAX(created_at) FROM releases WHERE capability_id=? AND family=? AND scope='family'",
                                  (capability_id, family)).fetchone()
        return float(row[0] or 0.0)

    def status(self, *, capability_id: str, candidate_digest: str, family: str = "") -> Dict[str, object]:
        c_cut = self._last_release(capability_id=capability_id, candidate_digest=candidate_digest, family=family, scope="candidate")
        f_cut = self._last_release(capability_id=capability_id, candidate_digest=candidate_digest, family=family, scope="family") if family else 0.0
        with closing(sqlite3.connect(self.path)) as con:
            cc = con.execute("SELECT COUNT(*) FROM failures WHERE capability_id=? AND candidate_digest=? AND created_at>?",
                             (capability_id, candidate_digest, c_cut)).fetchone()[0]
            fc = 0
            if family:
                fc = con.execute("SELECT COUNT(*) FROM failures WHERE capability_id=? AND family=? AND created_at>?",
                                 (capability_id, family, f_cut)).fetchone()[0]
        q = cc >= self.candidate_threshold or (bool(family) and fc >= self.family_threshold)
        return {"quarantined": bool(q), "candidate_failures": int(cc), "family_failures": int(fc),
                "candidate_threshold": self.candidate_threshold, "family_threshold": self.family_threshold,
                "candidate_release_cutoff": c_cut, "family_release_cutoff": f_cut}

    def release_with_holdout(self, *, capability_id: str, candidate_digest: str, evidence_sha256: str,
                             holdout_score: float, baseline_score: float, verified: bool,
                             untouched_holdout: bool, family: str = "", scope: str = "candidate") -> Dict[str, object]:
        if scope not in {"candidate", "family"}:
            raise ValueError("scope must be candidate or family")
        if scope == "family" and not family:
            raise ValueError("family scope requires family")
        ev = str(evidence_sha256).lower()
        if not _HEX64.fullmatch(ev):
            raise ValueError("evidence_sha256 must be SHA-256 hex")
        if verified is not True or untouched_holdout is not True:
            raise ValueError("release requires verified untouched holdout evidence")
        hs = float(holdout_score); bs = float(baseline_score)
        if not 0 <= hs <= 1 or not 0 <= bs <= 1:
            raise ValueError("holdout scores must be in 0..1")
        if hs < self.min_holdout_score or hs < bs - self.max_regression:
            raise ValueError("holdout evidence does not clear release gate")
        before = self.status(capability_id=capability_id, candidate_digest=candidate_digest, family=family)
        if not before["quarantined"]:
            return {"released": False, "reason": "not_quarantined", "status": before}
        if scope == "candidate" and int(before["candidate_failures"]) < self.candidate_threshold:
            raise ValueError("candidate release cannot clear a family-only quarantine")
        if scope == "family" and int(before["family_failures"]) < self.family_threshold:
            raise ValueError("family release requires family quarantine evidence")
        release_id = uuid.uuid4().hex
        try:
            with closing(sqlite3.connect(self.path)) as con:
                con.execute("INSERT INTO releases VALUES(?,?,?,?,?,?,?,?,?)",
                            (release_id, capability_id, candidate_digest, family or "", scope, ev, hs, bs, time.time()))
                con.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("holdout evidence has already been used for a quarantine release") from exc
        after = self.status(capability_id=capability_id, candidate_digest=candidate_digest, family=family)
        return {"released": not bool(after["quarantined"]), "release_id": release_id,
                "evidence_sha256": ev, "scope": scope, "status": after}
