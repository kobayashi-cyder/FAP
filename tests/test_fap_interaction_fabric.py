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

    def test_dynamic_sparse_metadata_is_exposed_for_multiple_routes(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="general",
                channels=("chat",),
                probe=lambda request: 0.55,
                handler=lambda request, budget: {"reply": "general"},
                priority=0.5,
                capabilities=("general",),
                task_families=("chat",),
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="reasoning",
                channels=("chat",),
                probe=lambda request: 0.95,
                handler=lambda request, budget: {
                    "reply": "reasoned",
                    "confidence": 0.94,
                },
                priority=1.0,
                capabilities=("logic", "verification"),
                task_families=("chat",),
                task_forms=("multi_step",),
            )
        )

        result = fabric.dispatch(
            InteractionRequest(
                "solve this carefully",
                channel="chat",
                metadata={
                    "task_form": "multi_step",
                    "required_capabilities": ("logic", "verification"),
                    "uncertainty": 0.7,
                },
            )
        )

        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "reasoning")
        sparse = result.payload["interaction_fabric"]["dynamic_sparse"]
        self.assertGreater(sparse["possible_edges"], 0)
        self.assertTrue(sparse["primary_path"])
        self.assertGreaterEqual(sparse["step"], 1)

    def test_dynamic_sparse_learning_persists_across_dispatches(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="reader",
                channels=("chat",),
                probe=lambda request: 0.9,
                handler=lambda request, budget: {
                    "reply": "read",
                    "confidence": 0.95,
                },
                capabilities=("retrieval",),
                task_families=("chat",),
                task_forms=("reading",),
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="fallback",
                channels=("chat",),
                probe=lambda request: 0.6,
                handler=lambda request, budget: {"reply": "fallback"},
                capabilities=("general",),
                task_families=("chat",),
            )
        )
        request = InteractionRequest(
            "read this",
            channel="chat",
            metadata={
                "task_form": "reading",
                "required_capabilities": ("retrieval",),
            },
        )

        first = fabric.dispatch(request)
        second = fabric.dispatch(request)

        first_step = first.payload["interaction_fabric"]["dynamic_sparse"]["step"]
        second_step = second.payload["interaction_fabric"]["dynamic_sparse"]["step"]
        self.assertGreater(second_step, first_step)

    def test_zero_probe_route_is_not_selected_by_sparse_path(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="active",
                channels=("chat",),
                probe=lambda request: 0.9,
                handler=lambda request, budget: {"reply": "active"},
                capabilities=("general",),
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="other",
                channels=("chat",),
                probe=lambda request: 0.7,
                handler=lambda request, budget: {"reply": "other"},
                capabilities=("general",),
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="disabled",
                channels=("chat",),
                probe=lambda request: 0.0,
                handler=lambda request, budget: {"reply": "disabled"},
                capabilities=("verification",),
            )
        )

        result = fabric.dispatch(
            InteractionRequest(
                "x",
                metadata={
                    "required_capabilities": ("verification",),
                    "uncertainty": 0.9,
                },
            )
        )
        sparse = result.payload["interaction_fabric"]["dynamic_sparse"]
        self.assertNotIn("disabled", sparse["primary_path"])
        self.assertTrue(
            all(
                "disabled" not in path
                for path in sparse["alternative_paths"]
            )
        )

    def test_sparse_routing_preserves_decline_fallback_order(self):
        fabric = InteractionFabric()
        calls = []
        fabric.register(
            InteractionEndpoint(
                endpoint_id="primary",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: calls.append("primary") or None,
                priority=1.0,
                capabilities=("logic",),
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="secondary",
                channels=("chat",),
                probe=lambda request: 0.7,
                handler=lambda request, budget: calls.append("secondary") or {
                    "reply": "ok",
                    "confidence": 0.9,
                },
                priority=0.8,
                capabilities=("general",),
            )
        )
        result = fabric.dispatch(
            InteractionRequest(
                "x",
                metadata={"required_capabilities": ("logic",)},
            )
        )
        self.assertEqual(result.endpoint_id, "secondary")
        self.assertEqual(calls, ["primary", "secondary"])
        self.assertEqual(
            [attempt.state for attempt in result.attempts],
            ["declined", "handled"],
        )

    def test_r001_budget_expands_sparse_route_allowance_under_failure_pressure(self):
        fabric = InteractionFabric()
        for route_id in ("alpha", "beta", "gamma", "delta"):
            fabric.register(
                InteractionEndpoint(
                    endpoint_id=route_id,
                    channels=("chat",),
                    probe=lambda request, rid=route_id: 0.9,
                    handler=lambda request, budget, rid=route_id: {
                        "reply": rid,
                        "confidence": 0.9,
                    },
                    capabilities=("logic",),
                    failure_specialties=("verification",),
                )
            )

        easy = fabric.dispatch(InteractionRequest("x"))
        hard = fabric.dispatch(
            InteractionRequest(
                "x",
                pressure_hint=0.9,
                metadata={
                    "failure_classes": ("verification", "logic"),
                    "failure_counts": {
                        "verification": 6,
                        "logic": 4,
                    },
                    "uncertainty": 0.9,
                    "verifier_disagreement": 1.0,
                },
            )
        )
        easy_budget = easy.payload["interaction_fabric"]["dynamic_sparse"][
            "adaptive_route_budget"
        ]
        hard_budget = hard.payload["interaction_fabric"]["dynamic_sparse"][
            "adaptive_route_budget"
        ]
        self.assertGreater(hard_budget["routes"], easy_budget["routes"])
        self.assertGreaterEqual(hard_budget["steps"], easy_budget["steps"])
        self.assertGreaterEqual(hard_budget["verify"], easy_budget["verify"])

    def test_single_positive_route_keeps_legacy_dispatch(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="only",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: {"reply": "ok"},
            )
        )
        result = fabric.dispatch(InteractionRequest("x"))
        self.assertEqual(result.endpoint_id, "only")
        self.assertNotIn(
            "dynamic_sparse",
            result.payload["interaction_fabric"],
        )

    def test_empty_request_blocks(self):
        result = InteractionFabric().dispatch(InteractionRequest("   "))
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.attempts[0].reason, "empty_request")


if __name__ == "__main__":
    unittest.main()
