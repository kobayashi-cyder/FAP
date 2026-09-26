from __future__ import annotations

import unittest

from fap_session_continuity import (
    AdaptiveContextSelector,
    SessionRouteLedger,
)


class AdaptiveSessionContinuityTests(unittest.TestCase):
    def _history(self, turns: int, chars: int = 1200):
        rows = []
        for i in range(turns):
            rows.append(
                {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "text": f"turn-{i} " + ("x" * chars),
                    "meta": {
                        "intent": "chat",
                        "verdict": "OK",
                        "arbitrary_secret": "SHOULD_NOT_COPY",
                    },
                }
            )
        return rows

    def test_high_demand_retains_at_least_as_much_context(self):
        selector = AdaptiveContextSelector()
        history = self._history(80)

        low = selector.select("short", history, pressure_hint=0.0)
        high = selector.select(
            "\n".join(f"complex line {i} alpha beta gamma" for i in range(100)),
            history,
            pressure_hint=1.0,
        )

        self.assertGreaterEqual(high.selected_turns, low.selected_turns)
        self.assertGreaterEqual(high.selected_chars, low.selected_chars)
        self.assertGreater(high.budget.scale, low.budget.scale)
        self.assertLessEqual(high.selected_turns, selector.max_turns)
        self.assertLessEqual(
            high.selected_chars,
            selector.hard_context_chars,
        )

    def test_recent_context_is_kept_and_old_context_is_dropped(self):
        selector = AdaptiveContextSelector(
            max_turns=4,
            max_turn_chars=1000,
            hard_context_chars=4000,
        )
        history = [
            {"role": "user", "text": f"turn-{i}"}
            for i in range(10)
        ]
        selected = selector.select("continue", history)
        self.assertEqual(
            [row["text"] for row in selected.history],
            ["turn-6", "turn-7", "turn-8", "turn-9"],
        )
        self.assertEqual(selected.dropped_turns, 6)

    def test_context_normalization_does_not_copy_arbitrary_metadata(self):
        selector = AdaptiveContextSelector()
        selected = selector.select(
            "continue",
            [
                {
                    "role": "user",
                    "text": "hello",
                    "meta": {
                        "intent": "chat",
                        "arbitrary_secret": "SECRET_TOKEN",
                    },
                }
            ],
        )
        row = selected.history[0]
        self.assertEqual(row["meta"], {"intent": "chat"})
        self.assertNotIn("SECRET_TOKEN", repr(row))

    def test_oversized_single_turn_is_tail_truncated(self):
        selector = AdaptiveContextSelector(
            max_turn_chars=1000,
            hard_context_chars=4000,
        )
        selected = selector.select(
            "continue",
            [{"role": "assistant", "text": "A" * 5000}],
        )
        self.assertEqual(len(selected.history), 1)
        self.assertEqual(len(selected.history[0]["text"]), 1000)

    def test_route_ledger_stores_no_message_text_and_is_session_isolated(self):
        ledger = SessionRouteLedger(
            max_sessions=2,
            max_events_per_session=2,
        )
        ledger.record(
            "s1",
            "repository_inspect",
            route_tags=("semantic-fabric", "read-only"),
        )
        ledger.record("s2", "artifact_code_generator")
        first = ledger.snapshot("s1")
        second = ledger.snapshot("s2")

        self.assertEqual(
            [event.endpoint_id for event in first.events],
            ["repository_inspect"],
        )
        self.assertEqual(
            [event.endpoint_id for event in second.events],
            ["artifact_code_generator"],
        )
        rendered = repr(first.to_dict())
        self.assertNotIn("text", rendered.lower())
        self.assertNotIn("message", rendered.lower())

    def test_route_ledger_has_bounded_events_and_sessions(self):
        ledger = SessionRouteLedger(
            max_sessions=2,
            max_events_per_session=2,
        )
        for endpoint in ("a", "b", "c"):
            ledger.record("s1", endpoint)
        self.assertEqual(
            [e.endpoint_id for e in ledger.snapshot("s1").events],
            ["b", "c"],
        )

        ledger.record("s2", "x")
        ledger.record("s3", "y")
        self.assertEqual(ledger.snapshot("s1").events, ())

    def test_invalid_direct_session_id_fails_closed(self):
        ledger = SessionRouteLedger()
        with self.assertRaises(ValueError):
            ledger.record("../escape", "endpoint")


if __name__ == "__main__":
    unittest.main()
