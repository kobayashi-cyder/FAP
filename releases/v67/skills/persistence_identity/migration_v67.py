from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Dict

MIGRATION_ID = "v67_scoped_event_identity_v1"

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


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _table_sql(con: sqlite3.Connection, name: str) -> str:
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return str(row[0]) if row else ""


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
            "evidence_backup": _table_exists(con, "evidence_v66_backup"),
            "canary_backup": _table_exists(con, "canary_obs_v66_backup"),
            "migration_recorded": recorded,
        }


def migrate_v66_identity_schema(path: str) -> Dict[str, int]:
    """Atomically migrate only event identity scope while preserving attestation anti-reuse."""
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
                out = {"already_applied": 1, "evidence_rows": 0, "canary_rows": 0}
                if _table_exists(con, "evidence"):
                    out["evidence_rows"] = int(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0])
                if _table_exists(con, "canary_obs"):
                    out["canary_rows"] = int(con.execute("SELECT COUNT(*) FROM canary_obs").fetchone()[0])
                con.commit()
                return out

            out = {"already_applied": 0, "evidence_rows": 0, "canary_rows": 0}

            if _table_exists(con, "evidence"):
                if _table_exists(con, "evidence_v66_backup"):
                    raise RuntimeError("evidence_v66_backup already exists")
                con.execute(EVIDENCE_SHADOW)
                con.execute(
                    "INSERT INTO evidence_v67_shadow "
                    "SELECT event_id,capability_id,candidate_digest,stage_ratio,success,quality,latency,"
                    "attestation_id,wrapper_id,created_at FROM evidence"
                )
                old_n = int(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0])
                new_n = int(con.execute("SELECT COUNT(*) FROM evidence_v67_shadow").fetchone()[0])
                if old_n != new_n:
                    raise RuntimeError("evidence row-count mismatch")
                con.execute("ALTER TABLE evidence RENAME TO evidence_v66_backup")
                con.execute("ALTER TABLE evidence_v67_shadow RENAME TO evidence")
                out["evidence_rows"] = new_n

            if _table_exists(con, "canary_obs"):
                if _table_exists(con, "canary_obs_v66_backup"):
                    raise RuntimeError("canary_obs_v66_backup already exists")
                con.execute(CANARY_SHADOW)
                con.execute(
                    "INSERT INTO canary_obs_v67_shadow "
                    "SELECT event_id,capability_id,candidate_digest,stage_index,arm,success,quality,latency,created_at "
                    "FROM canary_obs"
                )
                old_n = int(con.execute("SELECT COUNT(*) FROM canary_obs").fetchone()[0])
                new_n = int(con.execute("SELECT COUNT(*) FROM canary_obs_v67_shadow").fetchone()[0])
                if old_n != new_n:
                    raise RuntimeError("canary row-count mismatch")
                con.execute("ALTER TABLE canary_obs RENAME TO canary_obs_v66_backup")
                con.execute("ALTER TABLE canary_obs_v67_shadow RENAME TO canary_obs")
                out["canary_rows"] = new_n

            con.execute(
                "INSERT INTO v67_migration_meta(migration_id) VALUES(?)", (MIGRATION_ID,)
            )
            con.commit()
            return out
        except Exception:
            con.rollback()
            raise


def rollback_v67_identity_schema(path: str) -> None:
    """Restore the exact legacy tables kept by the migration transaction."""
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            if _table_exists(con, "evidence_v66_backup"):
                if _table_exists(con, "evidence_v67_failed"):
                    con.execute("DROP TABLE evidence_v67_failed")
                if _table_exists(con, "evidence"):
                    con.execute("ALTER TABLE evidence RENAME TO evidence_v67_failed")
                con.execute("ALTER TABLE evidence_v66_backup RENAME TO evidence")

            if _table_exists(con, "canary_obs_v66_backup"):
                if _table_exists(con, "canary_obs_v67_failed"):
                    con.execute("DROP TABLE canary_obs_v67_failed")
                if _table_exists(con, "canary_obs"):
                    con.execute("ALTER TABLE canary_obs RENAME TO canary_obs_v67_failed")
                con.execute("ALTER TABLE canary_obs_v66_backup RENAME TO canary_obs")

            if _table_exists(con, "v67_migration_meta"):
                con.execute(
                    "DELETE FROM v67_migration_meta WHERE migration_id=?", (MIGRATION_ID,)
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
