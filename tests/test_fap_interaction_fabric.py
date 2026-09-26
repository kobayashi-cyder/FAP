from __future__ import annotations

import unittest

from fap_interaction_fabric import (
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)


class InteractionFabricTests(unittest.TestCase):
    def test_higher_effective_score_wins(self):
        fabric = InteractionFabric()
        calls = []

        fabric.register(
            InteractionEndpoint(
                endpoint_id="fallback",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: calls.append("fallback") or {"reply": "fallback"},
                priority=0.1,
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="specialist",
                channels=("chat",),
                probe=lambda request: 0.8,
                handler=lambda request, budget: calls.append("specialist") or {"reply": "specialist"},
                priority=1.0,
            )
        )

        result = fabric.dispatch(InteractionRequest("hello", channel="chat"))
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "specialist")
        self.assertEqual(result.payload["reply"], "specialist")
        self.assertEqual(calls, ["specialist"])
        self.assertIn("interaction_fabric", result.payload)

    def test_decline_falls_through_to_next_endpoint(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="first",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: None,
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="second",
                channels=("chat",),
                probe=lambda request: 0.8,
                handler=lambda request, budget: {"reply": "ok"},
            )
        )
        result = fabric.dispatch(InteractionRequest("hello"))
        self.assertEqual(result.endpoint_id, "second")
        self.assertEqual([a.state for a in result.attempts], ["declined", "handled"])

    def test_probe_and_handler_failures_are_sanitized(self):
        fabric = InteractionFabric()

        def bad_probe(request):
            raise RuntimeError("SECRET=/private/path")

        def bad_handler(request, budget):
            raise ValueError("TOKEN=secret")

        fabric.register(
            InteractionEndpoint(
                endpoint_id="bad-probe",
                channels=("chat",),
                probe=bad_probe,
                handler=lambda request, budget: {"reply": "never"},
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="bad-handler",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=bad_handler,
            )
        )
        result = fabric.dispatch(InteractionRequest("hello"))
        rendered = repr(result.to_dict())
        self.assertEqual(result.state, "unhandled")
        self.assertIn("RuntimeError", rendered)
        self.assertIn("ValueError", rendered)
        self.assertNotIn("SECRET", rendered)
        self.assertNotIn("private", rendered)
        self.assertNotIn("TOKEN", rendered)

    def test_channel_isolation_and_dynamic_registration(self):
        fabric = InteractionFabric()
        endpoint = InteractionEndpoint(
            endpoint_id="coding",
            channels=("coding",),
            probe=lambda request: 1.0,
            handler=lambda request, budget: {"reply": "coded"},
        )
        fabric.register(endpoint)
        chat = fabric.dispatch(InteractionRequest("x", channel="chat"))
        self.assertEqual(chat.state, "unhandled")

        coding = fabric.dispatch(InteractionRequest("x", channel="coding"))
        self.assertEqual(coding.state, "handled")
        self.assertEqual(coding.endpoint_id, "coding")

        fabric.unregister("coding")
        self.assertEqual(fabric.endpoint_ids, ())

    def test_invalid_probe_score_is_rejected_not_executed(self):
        fabric = InteractionFabric()
        calls = []
        fabric.register(
            InteractionEndpoint(
                endpoint_id="invalid",
                channels=("chat",),
                probe=lambda request: 2.0,
                handler=lambda request, budget: calls.append(True) or {},
            )
        )
        result = fabric.dispatch(InteractionRequest("hello"))
        self.assertEqual(result.state, "unhandled")
        self.assertEqual(calls, [])
        self.assertEqual(result.attempts[0].state, "probe_rejected")

    def test_empty_request_blocks(self):
        result = InteractionFabric().dispatch(InteractionRequest("   "))
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.attempts[0].reason, "empty_request")


if __name__ == "__main__":
    unittest.main()
