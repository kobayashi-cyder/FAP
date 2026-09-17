from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Dict

MIGRATION_ID = "v67_scoped_event_identity_v2"

EVIDENCE_SHADOW = """
CREATE TABLE evidence_v67_shadow(
    event_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    candidate_digest TEXT NOT NULL,
    stage_ratio REAL NOT NULL,
    success INT NOT NULL,
    quality REAL NOT NULL,
    latency REAL NOT NULL,
    attestation_id TEXT NOT NULL UNIQUE,
    wrapper_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(capability_id, event_id)
)
"""

CANARY_SHADOW = """
CREATE TABLE canary_obs_v67_shadow(
    event_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    candidate_digest TEXT NOT NULL,
    stage_index INTEGER NOT NULL,
    arm TEXT NOT NULL,
    success INTEGER NOT NULL,
    quality REAL NOT NULL,
    latency REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(capability_id, event_id)
)
"""

FAILURES_SHADOW = """
CREATE TABLE failures_v67_shadow(
    event_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    candidate_digest TEXT NOT NULL,
    family TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(capability_id, event_id)
)
"""


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _table_sql(con: sqlite3.Connection, name: str) -> str:
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return str(row[0]) if row else ""


def _count(con: sqlite3.Connection, name: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) if _table_exists(con, name) else 0


def schema_state(path: str) -> Dict[str, object]:
    with closing(sqlite3.connect(path)) as con:
        meta_exists = _table_exists(con, "v67_migration_meta")
        recorded = bool(
            meta_exists
            and con.execute(
                "SELECT 1 FROM v67_migration_meta WHERE migration_id=?", (MIGRATION_ID,)
            ).fetchone()
        )
        return {
            "evidence": _table_sql(con, "evidence"),
            "canary_obs": _table_sql(con, "canary_obs"),
            "failures": _table_sql(con, "failures"),
            "evidence_backup": _table_exists(con, "evidence_v66_backup"),
            "canary_backup": _table_exists(con, "canary_obs_v66_backup"),
            "failures_backup": _table_exists(con, "failures_v66_backup"),
            "migration_recorded": recorded,
        }


def _swap_shadow(con: sqlite3.Connection, *, live: str, shadow: str, backup: str) -> int:
    if not _table_exists(con, live):
        return 0
    if _table_exists(con, backup):
        raise RuntimeError(f"{backup} already exists")
    old_n = _count(con, live)
    new_n = _count(con, shadow)
    if old_n != new_n:
        raise RuntimeError(f"{live} row-count mismatch")
    con.execute(f"ALTER TABLE {live} RENAME TO {backup}")
    con.execute(f"ALTER TABLE {shadow} RENAME TO {live}")
    return new_n


def migrate_v66_identity_schema(path: str) -> Dict[str, int]:
    """Atomically scope event IDs per capability without weakening proof/evidence anti-reuse."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS v67_migration_meta("
                "migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            if con.execute(
                "SELECT 1 FROM v67_migration_meta WHERE migration_id=?", (MIGRATION_ID,)
            ).fetchone():
                out = {
                    "already_applied": 1,
                    "evidence_rows": _count(con, "evidence"),
                    "canary_rows": _count(con, "canary_obs"),
                    "failure_rows": _count(con, "failures"),
                }
                con.commit()
                return out

            out = {"already_applied": 0, "evidence_rows": 0, "canary_rows": 0, "failure_rows": 0}

            if _table_exists(con, "evidence"):
                con.execute(EVIDENCE_SHADOW)
                con.execute(
                    "INSERT INTO evidence_v67_shadow "
                    "SELECT event_id,capability_id,candidate_digest,stage_ratio,success,quality,latency,"
                    "attestation_id,wrapper_id,created_at FROM evidence"
                )
                out["evidence_rows"] = _swap_shadow(
                    con, live="evidence", shadow="evidence_v67_shadow", backup="evidence_v66_backup"
                )

            if _table_exists(con, "canary_obs"):
                con.execute(CANARY_SHADOW)
                con.execute(
                    "INSERT INTO canary_obs_v67_shadow "
                    "SELECT event_id,capability_id,candidate_digest,stage_index,arm,success,quality,latency,created_at "
                    "FROM canary_obs"
                )
                out["canary_rows"] = _swap_shadow(
                    con, live="canary_obs", shadow="canary_obs_v67_shadow", backup="canary_obs_v66_backup"
                )

            if _table_exists(con, "failures"):
                con.execute(FAILURES_SHADOW)
                con.execute(
                    "INSERT INTO failures_v67_shadow "
                    "SELECT event_id,capability_id,candidate_digest,family,reason,created_at FROM failures"
                )
                out["failure_rows"] = _swap_shadow(
                    con, live="failures", shadow="failures_v67_shadow", backup="failures_v66_backup"
                )

            # Deliberately leave releases.evidence_sha256 UNIQUE globally: one holdout proof cannot clear two quarantines.
            con.execute(
                "INSERT INTO v67_migration_meta(migration_id) VALUES(?)", (MIGRATION_ID,)
            )
            con.commit()
            return out
        except Exception:
            con.rollback()
            raise


def _restore_backup(con: sqlite3.Connection, *, live: str, backup: str, failed: str) -> None:
    if not _table_exists(con, backup):
        return
    if _table_exists(con, failed):
        con.execute(f"DROP TABLE {failed}")
    if _table_exists(con, live):
        con.execute(f"ALTER TABLE {live} RENAME TO {failed}")
    con.execute(f"ALTER TABLE {backup} RENAME TO {live}")


def rollback_v67_identity_schema(path: str) -> None:
    """Restore exact V66 tables retained by the migration transaction."""
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            _restore_backup(con, live="evidence", backup="evidence_v66_backup", failed="evidence_v67_failed")
            _restore_backup(con, live="canary_obs", backup="canary_obs_v66_backup", failed="canary_obs_v67_failed")
            _restore_backup(con, live="failures", backup="failures_v66_backup", failed="failures_v67_failed")
            if _table_exists(con, "v67_migration_meta"):
                con.execute(
                    "DELETE FROM v67_migration_meta WHERE migration_id=?", (MIGRATION_ID,)
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
