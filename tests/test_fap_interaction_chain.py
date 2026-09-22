from __future__ import annotations

import unittest

from fap_interaction_chain import (
    InteractionChainCoordinator,
    InteractionHandoff,
)
from fap_interaction_fabric import (
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)


class InteractionChainTests(unittest.TestCase):
    def _fabric(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="conversation",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: {
                    "reply": "conversation result",
                    "route_tags": ["analysis-ready"],
                },
            )
        )
        fabric.register(
            InteractionEndpoint(
                endpoint_id="coding",
                channels=("coding",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: {
                    "reply": "coding result",
                    "route_tags": ["verified-code"],
                },
            )
        )
        return fabric

    def test_policy_connects_chat_to_coding_without_hardcoded_flow(self):
        fabric = self._fabric()
        chain = InteractionChainCoordinator(fabric)

        def policy(request, dispatch, index):
            if index == 0:
                return InteractionHandoff(
                    request=InteractionRequest(
                        text="implement the verified change",
                        history=request.history + ({"content": dispatch.payload["reply"]},),
                        channel="coding",
                    ),
                    allow_endpoint_ids=("coding",),
                    reason="specialist_handoff",
                )
            return None

        result = chain.run(
            InteractionRequest("analyze this request", channel="chat"),
            policy,
        )
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.reason, "chain_complete")
        self.assertEqual(
            [step.endpoint_id for step in result.steps],
            ["conversation", "coding"],
        )
        self.assertEqual(result.final_payload["reply"], "coding result")

    def test_endpoint_revisit_is_blocked_by_default(self):
        fabric = InteractionFabric()
        fabric.register(
            InteractionEndpoint(
                endpoint_id="loop",
                channels=("chat",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: {"reply": "again"},
            )
        )
        chain = InteractionChainCoordinator(fabric, max_steps=4)

        def policy(request, dispatch, index):
            return InteractionHandoff(
                request=InteractionRequest("again", channel="chat"),
                allow_endpoint_ids=("loop",),
                reason="repeat",
            )

        result = chain.run(InteractionRequest("start"), policy)
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.reason, "handoff_unhandled")
        self.assertEqual(len(result.steps), 1)

    def test_policy_error_is_sanitized(self):
        fabric = self._fabric()

        def policy(request, dispatch, index):
            raise RuntimeError("SECRET=/private/path")

        result = InteractionChainCoordinator(fabric).run(
            InteractionRequest("start", channel="chat"),
            policy,
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason, "handoff_policy_failed:RuntimeError")
        self.assertNotIn("SECRET", repr(result.to_dict()))
        self.assertNotIn("private", repr(result.to_dict()))

    def test_oversized_handoff_is_blocked(self):
        fabric = self._fabric()

        def policy(request, dispatch, index):
            return InteractionHandoff(
                request=InteractionRequest(
                    "x" * 300_000,
                    channel="coding",
                ),
                allow_endpoint_ids=("coding",),
                reason="oversized",
            )

        result = InteractionChainCoordinator(fabric).run(
            InteractionRequest("start", channel="chat"),
            policy,
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(
            result.reason,
            "handoff_text_exceeds_context_budget",
        )

    def test_explicit_step_limit_stops_chain(self):
        fabric = self._fabric()
        chain = InteractionChainCoordinator(
            fabric,
            max_steps=1,
            allow_revisit=True,
        )

        def policy(request, dispatch, index):
            return InteractionHandoff(
                request=InteractionRequest(
                    "next",
                    channel="coding",
                ),
                allow_endpoint_ids=("coding",),
                reason="continue",
            )

        result = chain.run(
            InteractionRequest("start", channel="chat"),
            policy,
        )
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.reason, "chain_step_limit_reached")
        self.assertEqual(len(result.steps), 1)

    def test_allowlist_selects_only_requested_endpoint(self):
        fabric = InteractionFabric()
        calls = []
        for endpoint_id in ("a", "b"):
            fabric.register(
                InteractionEndpoint(
                    endpoint_id=endpoint_id,
                    channels=("chat",),
                    probe=lambda request: 1.0,
                    handler=lambda request, budget, eid=endpoint_id: (
                        calls.append(eid) or {"reply": eid}
                    ),
                )
            )
        result = fabric.dispatch(
            InteractionRequest("x"),
            allow_endpoint_ids=("b",),
        )
        self.assertEqual(result.endpoint_id, "b")
        self.assertEqual(calls, ["b"])


if __name__ == "__main__":
    unittest.main()
