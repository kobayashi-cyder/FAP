from __future__ import annotations

import unittest

import fap_v87_76_session_continuity_gateway as g
from fap_interaction_fabric import InteractionEndpoint, InteractionRequest


class V8776SessionGatewayTests(unittest.TestCase):
    def setUp(self):
        self.core = g.FAPV8776Unified()
        self.sid = "v8776-session-test"
        self.path = g.base.MEMORY.path(self.sid)
        if hasattr(g.base.MEMORY, "clear"):
            g.base.MEMORY.clear(self.sid)
        elif self.path.exists():
            self.path.unlink()
        self.chapter_path = self.core._chapter_path(self.sid)
        if self.chapter_path.exists():
            self.chapter_path.unlink()
        if hasattr(self.core.goal_state, "clear"):
            self.core.goal_state.clear(self.sid)

    def tearDown(self):
        if hasattr(g.base.MEMORY, "clear"):
            g.base.MEMORY.clear(self.sid)
        elif self.path.exists():
            self.path.unlink()
        if self.chapter_path.exists():
            self.chapter_path.unlink()
        if hasattr(self.core.goal_state, "clear"):
            self.core.goal_state.clear(self.sid)
        self.core.clear_route_continuity(self.sid)

    def test_builtin_repository_inspect_endpoint_dispatches(self):
        dispatched = self.core.interactions.dispatch(
            InteractionRequest(
                "リポジトリを解析して",
                channel="chat",
            )
        )
        self.assertEqual(
            dispatched.endpoint_id,
            "repository_inspect",
            repr(dispatched.to_dict()),
        )
        self.assertEqual(dispatched.state, "handled", repr(dispatched.to_dict()))

    def test_existing_session_store_is_reused_with_adaptive_context(self):
        first = self.core.chat("リポジトリを解析して", self.sid)
        second = self.core.chat("リポジトリを分析して", self.sid)

        self.assertIn("adaptive_session_context", first)
        self.assertIn("adaptive_session_context", second)
        self.assertGreaterEqual(
            second["adaptive_session_context"]["source_turns"],
            first["adaptive_session_context"]["source_turns"],
        )

        persisted = g.base.MEMORY.load(self.sid)
        self.assertGreaterEqual(len(persisted), 4)
        self.assertTrue(
            any(row.get("text") == "リポジトリを解析して" for row in persisted)
        )

        events = second["session_route_continuity"]["events"]
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[-1]["endpoint_id"], "repository_inspect")

    def test_previous_endpoint_metadata_is_available_to_next_endpoint(self):
        self.core.chat("リポジトリを解析して", self.sid)
        captured = {}

        def handler(request, budget):
            captured.update(dict(request.metadata or {}))
            return {
                "ok": True,
                "reply": "custom inspected",
                "confidence": 0.99,
                "route_tags": ["custom-route"],
            }

        self.core.register_semantic_endpoint(
            InteractionEndpoint(
                endpoint_id="continuity_probe",
                channels=("chat",),
                probe=lambda request: 0.0,
                handler=handler,
                priority=10.0,
                cost=1.0,
            ),
            ("repository_inspect",),
        )

        result = self.core.chat("リポジトリを分析して", self.sid)
        continuity = captured.get("session_continuity") or {}
        self.assertIn(
            "repository_inspect",
            continuity.get("recent_endpoints", []),
        )
        self.assertEqual(
            result["session_route_continuity"]["events"][-1]["endpoint_id"],
            "continuity_probe",
        )

    def test_sessions_do_not_share_endpoint_continuity(self):
        other = "v8776-other-session"
        other_path = g.base.MEMORY.path(other)
        if other_path.exists():
            other_path.unlink()
        try:
            self.core.chat("リポジトリを解析して", self.sid)
            snapshot = self.core.session_routes.snapshot(other)
            self.assertEqual(snapshot.events, ())
        finally:
            if other_path.exists():
                other_path.unlink()
            self.core.clear_route_continuity(other)

    def test_new_chapter_purges_pre_boundary_history_and_goal_state(self):
        g.base.MEMORY.append_exchange(
            self.sid,
            "旧章の本文です",
            "旧章の回答です",
        )
        self.core.goal_state.update(
            self.sid,
            "目標は旧章の作業を完成させる",
        )
        self.core.session_routes.record(
            self.sid,
            "old_endpoint",
            route_tags=("old",),
        )

        result = self.core.chat("新章: 新しい話題です", self.sid)

        persisted = g.base.MEMORY.load(self.sid)
        persisted_text = "\n".join(str(row.get("text", "")) for row in persisted)
        self.assertNotIn("旧章の本文です", persisted_text)
        self.assertNotIn("旧章の回答です", persisted_text)
        self.assertIn("新章: 新しい話題です", persisted_text)

        state = self.core.goal_state.load(self.sid)
        self.assertEqual(state.get("open_goal"), "")
        self.assertEqual(state.get("goals"), [])

        events = result["session_route_continuity"]["events"]
        self.assertFalse(
            any(event.get("endpoint_id") == "old_endpoint" for event in events)
        )

        marker = result.get("chapter_boundary") or {}
        self.assertEqual(marker.get("context_epoch"), 1)
        self.assertTrue(marker.get("chapter_started_at"))

    def test_each_new_chapter_replaces_previous_chapter_history(self):
        first = self.core.chat("新章: 第一章です", self.sid)
        first_marker = first.get("chapter_boundary") or {}
        self.assertEqual(first_marker.get("context_epoch"), 1)

        self.core.chat("第一章の続きです", self.sid)
        second = self.core.chat("新章: 第二章です", self.sid)
        second_marker = second.get("chapter_boundary") or {}
        self.assertEqual(second_marker.get("context_epoch"), 2)

        persisted = g.base.MEMORY.load(self.sid)
        persisted_text = "\n".join(str(row.get("text", "")) for row in persisted)
        self.assertNotIn("第一章の続きです", persisted_text)
        self.assertIn("新章: 第二章です", persisted_text)

    def test_status_reports_no_new_message_store(self):
        status = self.core.status()["session_continuity"]
        self.assertTrue(status["enabled"])
        self.assertTrue(status["existing_persistent_message_store_reused"])
        self.assertFalse(status["new_message_store_added"])
        self.assertFalse(status["route_ledger_stores_message_text"])
        self.assertFalse(status["fca_required"])


if __name__ == "__main__":
    unittest.main()
