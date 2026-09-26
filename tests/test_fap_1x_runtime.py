from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from fap_1x_runtime import FAP1xRuntime


class _CodingResult:
    def __init__(self, state: str):
        self.state = state

    def to_dict(self):
        return {"state": self.state}


class _CodingCoordinator:
    def __init__(self, state: str = "verified_candidate"):
        self.state = state
        self.calls = []

    def run(self, goal, proposer, commands, **kwargs):
        self.calls.append((goal, proposer, tuple(commands), kwargs))
        return _CodingResult(self.state)


class FAP1xRuntimeTests(unittest.TestCase):
    def test_plain_text_endpoint_roundtrip(self):
        runtime = FAP1xRuntime()
        runtime.register_text_endpoint("echo", lambda text: "echo:" + text)
        self.assertEqual(runtime.chat("hello"), "echo:hello")

    def test_unhandled_is_fail_closed(self):
        runtime = FAP1xRuntime()
        self.assertEqual(runtime.chat("hello"), "")
        self.assertEqual(runtime.dispatch("hello").state, "unhandled")

    def test_probe_can_select_specialist(self):
        runtime = FAP1xRuntime()
        runtime.register_text_endpoint(
            "general",
            lambda text: "general",
            probe=lambda _text: 0.2,
        )
        runtime.register_text_endpoint(
            "math",
            lambda text: "math",
            probe=lambda text: 1.0 if "2+2" in text else 0.0,
        )
        result = runtime.dispatch("2+2")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "math")
        self.assertEqual(result.payload["text"], "math")

    def test_session_history_reaches_contextual_endpoint(self):
        runtime = FAP1xRuntime(max_history_messages=8)

        def contextual(request, _budget):
            return {"text": str(len(request.history)), "ok": True}

        runtime.register_endpoint("context", contextual)
        self.assertEqual(runtime.chat("one", session_id="s"), "0")
        self.assertEqual(runtime.chat("two", session_id="s"), "2")

    def test_session_history_is_bounded(self):
        runtime = FAP1xRuntime(max_history_messages=4)
        runtime.register_text_endpoint("echo", lambda text: text)
        for i in range(5):
            runtime.chat(str(i), session_id="bounded")
        snapshot = runtime.session_snapshot("bounded")
        self.assertEqual(len(snapshot), 4)
        self.assertEqual(snapshot[-1]["content"], "4")

    def test_semantic_memory_is_injected_into_later_turn(self):
        with TemporaryDirectory() as root:
            runtime = FAP1xRuntime(memory_root=root)

            def contextual(request, _budget):
                memory = tuple((request.metadata or {}).get("memory_context", ()))
                return {"text": " | ".join(memory), "ok": True}

            runtime.register_endpoint("context", contextual)
            runtime.chat("回答言語は日本語にする", session_id="mem")
            reply = runtime.chat("回答言語の設定を教えて", session_id="mem")
            self.assertIn("日本語", reply)

    def test_verified_tool_failure_falls_through(self):
        runtime = FAP1xRuntime()
        runtime.register_tool_endpoint(
            "bad",
            lambda _text, _meta: {"text": "wrong", "value": 3},
            verifier=lambda payload: payload.get("value") == 4,
            priority=2.0,
        )
        runtime.register_tool_endpoint(
            "good",
            lambda _text, _meta: {"text": "right", "value": 4},
            verifier=lambda payload: payload.get("value") == 4,
            priority=1.0,
        )
        result = runtime.tool_turn("calculate")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "good")
        self.assertEqual(result.payload["text"], "right")
        self.assertIn("rejected", [attempt.state for attempt in result.attempts])

    def test_auto_turn_selects_verified_calculation_tool(self):
        runtime = FAP1xRuntime()
        runtime.register_tool_endpoint(
            "calculator",
            lambda _text, metadata: {
                "text": "4",
                "value": 4,
                "auto_channel": metadata.get("auto_channel"),
            },
            verifier=lambda payload: payload.get("value") == 4,
            capabilities=("tool", "calculator"),
            task_forms=("calculation",),
        )
        result = runtime.auto_turn("calculate 2 + 2")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "calculator")
        self.assertEqual(result.payload["text"], "4")
        self.assertEqual(result.payload["auto_channel"], "tool")

    def test_auto_turn_selects_repository_coding_channel(self):
        runtime = FAP1xRuntime()
        coordinator = _CodingCoordinator()
        runtime.register_repository_coding_endpoint(
            "coder",
            coordinator,
            proposer=object(),
            commands=("compile",),
        )
        result = runtime.auto_turn("fix parser.py bug and verify tests")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "coder")
        self.assertEqual(result.payload["state"], "verified_candidate")

    def test_auto_turn_keeps_general_request_on_chat(self):
        runtime = FAP1xRuntime()
        runtime.register_text_endpoint("chat", lambda text: "chat:" + text)
        runtime.register_tool_endpoint(
            "special-tool",
            lambda _text, _meta: {"text": "tool"},
            capabilities=("image",),
            task_forms=("vision",),
        )
        result = runtime.auto_turn("hello there")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "chat")
        self.assertEqual(result.payload["text"], "chat:hello there")

    def test_repository_coding_adapter_uses_common_dispatch(self):
        runtime = FAP1xRuntime()
        coordinator = _CodingCoordinator()
        proposer = object()
        runtime.register_repository_coding_endpoint(
            "coder",
            coordinator,
            proposer,
            commands=("compile",),
        )
        result = runtime.coding_turn("fix target.py")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "coder")
        self.assertEqual(result.payload["state"], "verified_candidate")
        self.assertEqual(coordinator.calls[0][0], "fix target.py")


if __name__ == "__main__":
    unittest.main()
