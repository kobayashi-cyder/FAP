import sqlite3
import tempfile
import unittest
from pathlib import Path

from migration_v67 import migrate_v66_identity_schema, rollback_v67_identity_schema, schema_state


def make_v66_fixture(path: str) -> None:
    with sqlite3.connect(path) as con:
        con.executescript(
            """
            CREATE TABLE evidence(
                event_id TEXT PRIMARY KEY,
                capability_id TEXT NOT NULL,
                candidate_digest TEXT NOT NULL,
                stage_ratio REAL NOT NULL,
                success INT NOT NULL,
                quality REAL NOT NULL,
                latency REAL NOT NULL,
                attestation_id TEXT NOT NULL UNIQUE,
                wrapper_id TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE canary_obs(
                event_id TEXT PRIMARY KEY,
                capability_id TEXT NOT NULL,
                candidate_digest TEXT NOT NULL,
                stage_index INTEGER NOT NULL,
                arm TEXT NOT NULL,
                success INTEGER NOT NULL,
                quality REAL NOT NULL,
                latency REAL NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        con.execute(
            "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("event-1", "cap-a", "digest-a", 0.05, 1, 0.9, 10.0, "att-a", "wrapper", 1.0),
        )
        con.execute(
            "INSERT INTO canary_obs VALUES(?,?,?,?,?,?,?,?,?)",
            ("obs-1", "cap-a", "digest-a", 0, "active", 1, 0.9, 10.0, 1.0),
        )


class V67MigrationTests(unittest.TestCase):
    def test_migration_preserves_rows_and_scopes_event_ids(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "state.sqlite3")
            make_v66_fixture(path)
            result = migrate_v66_identity_schema(path)
            self.assertEqual(result["evidence_rows"], 1)
            self.assertEqual(result["canary_rows"], 1)
            with sqlite3.connect(path) as con:
                con.execute(
                    "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("event-1", "cap-b", "digest-b", 0.05, 1, 0.8, 11.0, "att-b", "wrapper", 2.0),
                )
                con.execute(
                    "INSERT INTO canary_obs VALUES(?,?,?,?,?,?,?,?,?)",
                    ("obs-1", "cap-b", "digest-b", 0, "active", 1, 0.8, 11.0, 2.0),
                )
                self.assertEqual(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM canary_obs").fetchone()[0], 2)

    def test_migration_keeps_attestation_globally_single_use(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "state.sqlite3")
            make_v66_fixture(path)
            migrate_v66_identity_schema(path)
            with sqlite3.connect(path) as con:
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute(
                        "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("event-2", "cap-b", "digest-b", 0.05, 1, 0.8, 11.0, "att-a", "wrapper", 2.0),
                    )

    def test_restart_is_idempotent_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "state.sqlite3")
            make_v66_fixture(path)
            migrate_v66_identity_schema(path)
            first = schema_state(path)
            result = migrate_v66_identity_schema(path)
            second = schema_state(path)
            self.assertEqual(result["already_applied"], 1)
            self.assertEqual(first, second)
            self.assertTrue(second["evidence_backup"])
            self.assertTrue(second["canary_backup"])
            self.assertTrue(second["migration_recorded"])

    def test_rollback_restores_v66_global_event_identity(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "state.sqlite3")
            make_v66_fixture(path)
            migrate_v66_identity_schema(path)
            rollback_v67_identity_schema(path)
            with sqlite3.connect(path) as con:
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute(
                        "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("event-1", "cap-b", "digest-b", 0.05, 1, 0.8, 11.0, "att-b", "wrapper", 2.0),
                    )
                self.assertEqual(con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
