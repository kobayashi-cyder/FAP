from __future__ import annotations

import unittest

import fap_v87_76_session_continuity_gateway as g
from fap_interaction_fabric import InteractionEndpoint, InteractionRequest


class V8776SessionGatewayTests(unittest.TestCase):
    def setUp(self):
        self.core = g.FAPV8776Unified()
        self.sid = "v8776-session-test"
        self.path = g.base.MEMORY.path(self.sid)
        if self.path.exists():
            self.path.unlink()

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()
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

    def test_status_reports_no_new_message_store(self):
        status = self.core.status()["session_continuity"]
        self.assertTrue(status["enabled"])
        self.assertTrue(status["existing_persistent_message_store_reused"])
        self.assertFalse(status["new_message_store_added"])
        self.assertFalse(status["route_ledger_stores_message_text"])
        self.assertFalse(status["fca_required"])


if __name__ == "__main__":
    unittest.main()
