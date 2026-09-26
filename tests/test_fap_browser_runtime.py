from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest

from fap_browser_runtime import (
    BrowserRuntimeJournal,
    BrowserRuntimeState,
    RUNTIME_VERSION,
    RuntimeLock,
    RuntimeStateStore,
    _safe_url_metadata,
)


class RuntimeStateTests(unittest.TestCase):
    def test_state_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            store = RuntimeStateStore(path)
            state = BrowserRuntimeState(
                version=RUNTIME_VERSION,
                state="running",
                branch="side/1.0.01-test",
                goal_sha256="a" * 64,
                updated_unix=123.0,
                pid=1234,
                host="test-host",
                cdp_url="http://127.0.0.1:9222",
                last_url="https://chatgpt.com/",
                restart_count=2,
            )
            store.write(state)
            self.assertEqual(store.read(), state)

    def test_url_metadata_strips_query_and_fragment(self) -> None:
        self.assertEqual(
            _safe_url_metadata("https://example.com/path?token=secret#frag"),
            "https://example.com/path",
        )
        self.assertEqual(_safe_url_metadata("file:///tmp/private"), "")


class RuntimeLockTests(unittest.TestCase):
    def test_second_controller_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.lock"
            first = RuntimeLock(path)
            second = RuntimeLock(path)
            first.acquire()
            try:
                with self.assertRaisesRegex(RuntimeError, "another FAP"):
                    second.acquire()
            finally:
                first.release()

    def test_stale_dead_process_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.lock"
            path.write_text(
                json.dumps(
                    {
                        "pid": 99999999,
                        "host": socket.gethostname(),
                        "created_unix": time.time() - 1000,
                    }
                ),
                encoding="utf-8",
            )
            lock = RuntimeLock(path, stale_after_sec=60)
            lock.acquire()
            try:
                self.assertTrue(lock.acquired)
            finally:
                lock.release()


class RuntimeJournalTests(unittest.TestCase):
    def test_restart_count_tracks_interrupted_same_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            first = BrowserRuntimeJournal(
                runtime_dir,
                branch="side/1.0.01-test",
                goal="improve browser",
                cdp_url="http://127.0.0.1:9222",
            )
            first.lock.acquire()
            try:
                first.update("running")
            finally:
                first.lock.release()

            with BrowserRuntimeJournal(
                runtime_dir,
                branch="side/1.0.01-test",
                goal="improve browser",
                cdp_url="http://127.0.0.1:9222",
            ) as second:
                self.assertEqual(second.restart_count, 1)
                state = second.update("chatgpt_ready")
                self.assertEqual(state.restart_count, 1)

    def test_goal_text_is_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret_goal = "private goal text should not be stored verbatim"
            with BrowserRuntimeJournal(
                tmp,
                branch="side/1.0.01-test",
                goal=secret_goal,
                cdp_url="http://127.0.0.1:9222",
            ) as journal:
                journal.update("running")
            persisted = (Path(tmp) / "state.json").read_text(encoding="utf-8")
            self.assertNotIn(secret_goal, persisted)
            self.assertIn("goal_sha256", persisted)


if __name__ == "__main__":
    unittest.main()
