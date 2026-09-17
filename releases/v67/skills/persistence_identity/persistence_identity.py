from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Dict


def scoped_identity(capability_id: str, local_id: str, *, namespace: str = "event") -> str:
    """Return a stable identity scoped to one capability and namespace."""
    cap = str(capability_id).strip()
    lid = str(local_id).strip()
    ns = str(namespace).strip()
    if not cap or not lid or not ns:
        raise ValueError("capability_id, local_id and namespace are required")
    body = json.dumps(
        {"v": 1, "namespace": ns, "capability_id": cap, "local_id": lid},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class ScopedEvidenceLedger:
    """Prototype V67 ledger that proves IDs do not collide across capabilities."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence(
                    capability_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL,
                    attestation_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(capability_id, event_id),
                    UNIQUE(capability_id, attestation_id)
                );
                """
            )
            row = con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO metadata(key,value) VALUES('schema_version',?)",
                    (str(self.SCHEMA_VERSION),),
                )
            elif int(row[0]) != self.SCHEMA_VERSION:
                raise RuntimeError(f"unsupported schema version: {row[0]}")
            con.commit()

    def insert(
        self,
        *,
        capability_id: str,
        event_id: str,
        candidate_digest: str,
        attestation_id: str,
        payload: Dict[str, object],
    ) -> bool:
        values = [capability_id, event_id, candidate_digest, attestation_id]
        if any(not str(v).strip() for v in values):
            raise ValueError("identity fields must be non-empty")
        try:
            with closing(sqlite3.connect(self.path)) as con:
                con.execute(
                    """
                    INSERT INTO evidence(
                        capability_id,event_id,candidate_digest,attestation_id,payload_json
                    ) VALUES(?,?,?,?,?)
                    """,
                    (
                        str(capability_id),
                        str(event_id),
                        str(candidate_digest),
                        str(attestation_id),
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    ),
                )
                con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def counts(self) -> Dict[str, int]:
        with closing(sqlite3.connect(self.path)) as con:
            rows = con.execute(
                "SELECT capability_id, COUNT(*) FROM evidence GROUP BY capability_id ORDER BY capability_id"
            ).fetchall()
        return {str(cap): int(n) for cap, n in rows}
