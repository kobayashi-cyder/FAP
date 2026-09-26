from __future__ import annotations

import unittest

from fap_1x_runtime import FAP1xRuntime


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
        runtime.register_text_endpoint("general", lambda text: "general", probe=lambda _text: 0.2)
        runtime.register_text_endpoint("math", lambda text: "math", probe=lambda text: 1.0 if "2+2" in text else 0.0)
        result = runtime.dispatch("2+2")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "math")
        self.assertEqual(result.payload["text"], "math")


if __name__ == "__main__":
    unittest.main()
