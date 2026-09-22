from __future__ import annotations

import json
from pathlib import Path
import unittest

from fap_conversation_fuzz import (
    generate_conversation_corpus,
    is_nonfinite_number,
)
from fap_interaction_fabric import (
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)
from fap_semantic_action_router import SemanticActionRouter
from fap_semantic_conversation import SemanticConversationRouter
from fap_session_continuity import AdaptiveContextSelector


ROOT = Path(__file__).resolve().parents[1]


def _strict_json(value) -> None:
    json.dumps(value, ensure_ascii=False, allow_nan=False)


class ConversationFuzzTests(unittest.TestCase):
    def setUp(self):
        self.conversation_router = SemanticConversationRouter(ROOT)
        self.action_router = SemanticActionRouter(ROOT)
        self.selector = AdaptiveContextSelector()
        self.fabric = InteractionFabric()
        self.fabric.register(
            InteractionEndpoint(
                endpoint_id="fuzz-fallback",
                channels=("*",),
                probe=lambda request: 1.0,
                handler=lambda request, budget: {
                    "reply": str(request.text or "")[:128],
                    "route_tags": ["fuzz-generic"],
                },
            )
        )

    def test_randomized_corpus_is_broad_and_reproducible(self):
        first = tuple(generate_conversation_corpus(ROOT, seed=87078, count=256))
        second = tuple(generate_conversation_corpus(ROOT, seed=87078, count=256))
        self.assertEqual(
            [(x.index, x.text, x.channel) for x in first],
            [(x.index, x.text, x.channel) for x in second],
        )
        self.assertGreater(len({x.text for x in first}), 200)
        self.assertTrue(any(x.history is None for x in first))
        self.assertTrue(any(isinstance(x.history, int) for x in first))
        self.assertTrue(any(is_nonfinite_number(x.pressure_hint) for x in first))

    def test_randomized_conversation_boundaries_never_raise(self):
        for case in generate_conversation_corpus(ROOT, seed=8707801, count=1024):
            with self.subTest(case=case.index):
                semantic = self.conversation_router.match(case.text)
                action = self.action_router.match(case.text)
                if semantic is not None:
                    _strict_json(semantic)
                if action is not None:
                    _strict_json(action)

                selection = self.selector.select(
                    case.text,
                    case.history,
                    pressure_hint=case.pressure_hint,
                )
                self.assertLessEqual(
                    selection.selected_turns,
                    self.selector.max_turns,
                )
                self.assertLessEqual(
                    selection.selected_chars,
                    self.selector.hard_context_chars,
                )
                _strict_json(selection.history)
                _strict_json(selection.to_dict())

                dispatch = self.fabric.dispatch(
                    InteractionRequest(
                        text=case.text,
                        history=case.history,
                        channel=case.channel,
                        pressure_hint=case.pressure_hint,
                    )
                )
                self.assertIn(
                    dispatch.state,
                    {"blocked", "handled", "unhandled"},
                )
                _strict_json(dispatch.to_dict())


class V8778ConversationGatewayTests(unittest.TestCase):
    def test_latest_gateway_reports_generic_hardening(self):
        import fap_v87_78_conversation_fuzz_gateway as gateway

        status = gateway.CORE.chat_status()
        self.assertEqual(status.get("version"), "87.78-unified-chat")
        hardening = gateway.CORE.status().get("conversation_fuzz_hardening") or {}
        self.assertTrue(hardening.get("enabled"))
        self.assertTrue(hardening.get("knowledge_derived_corpus"))
        self.assertFalse(hardening.get("utterance_specific_branches_added"))
        self.assertTrue(hardening.get("strict_json_safe"))


if __name__ == "__main__":
    unittest.main()
