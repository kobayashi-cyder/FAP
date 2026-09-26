from __future__ import annotations

import json
import unittest

from fap_browser_operator import (
    BrowserChatReasoner,
    BrowserEvidence,
    BrowserSessionConfig,
    ChatGPTReadiness,
    _clean_result_url,
    _normalize_http_url,
    _parse_queries,
)
from fap_self_improvement_controller import _build_parser


class BrowserConfigTests(unittest.TestCase):
    def test_default_search_engine(self) -> None:
        config = BrowserSessionConfig()
        self.assertEqual(config.search_engine, "google")
        self.assertFalse(config.headless)

    def test_rejects_unsafe_cdp_scheme(self) -> None:
        with self.assertRaisesRegex(ValueError, "cdp_url"):
            BrowserSessionConfig(cdp_url="file:///tmp/socket")

    def test_only_http_urls_are_browsable(self) -> None:
        self.assertEqual(
            _normalize_http_url("https://example.com/a"),
            "https://example.com/a",
        )
        with self.assertRaisesRegex(ValueError, "http"):
            _normalize_http_url("javascript:alert(1)")
        self.assertEqual(_clean_result_url("mailto:test@example.com"), "")


class QueryParsingTests(unittest.TestCase):
    def test_json_queries_are_bounded_and_deduplicated(self) -> None:
        text = json.dumps(
            {"queries": ["playwright cdp", "playwright cdp", "chatgpt browser ui"]}
        )
        self.assertEqual(
            _parse_queries(text, "fallback", 3),
            ("playwright cdp", "chatgpt browser ui"),
        )

    def test_query_parser_falls_back_to_goal(self) -> None:
        self.assertEqual(
            _parse_queries("not-json", "  improve   browser  loop  ", 3),
            ("improve browser loop",),
        )


class FakeBrowser:
    def __init__(self) -> None:
        self.config = BrowserSessionConfig(max_search_results=2)
        self.started = 0
        self.closed = 0
        self.queries = []
        self.read = []

    def start(self):
        self.started += 1
        return self

    def close(self) -> None:
        self.closed += 1

    def is_healthy(self) -> bool:
        return self.started > 0 and self.closed == 0

    def search(self, query: str):
        self.queries.append(query)
        return (
            "https://docs.example/a",
            "https://docs.example/b",
        )

    def read_pages(self, urls):
        self.read.append(tuple(urls))
        return (
            BrowserEvidence(
                url="https://docs.example/a",
                title="A",
                text="Primary evidence A",
            ),
            BrowserEvidence(
                url="https://docs.example/b",
                title="B",
                text="Independent evidence B",
            ),
        )


class FakeChat:
    def __init__(self) -> None:
        self.prompts = []

    def wait_until_ready(self, timeout_sec: float):
        return ChatGPTReadiness(
            state="ready",
            url="https://chatgpt.com/",
            waited_sec=min(0.01, float(timeout_sec)),
        )

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return '{"queries":["query one","query two"]}'
        return "synthesized browser answer"


class BrowserReasonerTests(unittest.TestCase):
    def test_prepare_waits_for_chatgpt_ready(self) -> None:
        browser = FakeBrowser()
        reasoner = BrowserChatReasoner(browser=browser)
        reasoner.chat = FakeChat()

        readiness = reasoner.prepare(30)

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.state, "ready")
        self.assertTrue(reasoner.health())
        reasoner.close()

    def test_web_search_uses_real_browser_adapter_surface(self) -> None:
        browser = FakeBrowser()
        reasoner = BrowserChatReasoner(browser=browser, max_queries=2)
        reasoner.chat = FakeChat()

        result = reasoner.respond("Investigate browser automation", web_search=True)

        self.assertEqual(result.text, "synthesized browser answer")
        self.assertTrue(result.used_web_search)
        self.assertEqual(browser.queries, ["query one", "query two"])
        self.assertEqual(
            result.sources,
            ("https://docs.example/a", "https://docs.example/b"),
        )
        self.assertIn("BROWSER EVIDENCE", reasoner.chat.prompts[-1])
        reasoner.close()
        self.assertEqual(browser.closed, 1)

    def test_no_web_search_talks_to_chatgpt_ui_only(self) -> None:
        browser = FakeBrowser()
        reasoner = BrowserChatReasoner(browser=browser)
        chat = FakeChat()
        chat.ask = lambda prompt: "direct web-ui answer"
        reasoner.chat = chat

        result = reasoner.respond("hello", web_search=False)

        self.assertEqual(result.text, "direct web-ui answer")
        self.assertFalse(result.used_web_search)
        self.assertEqual(browser.queries, [])
        reasoner.close()


class CliTests(unittest.TestCase):
    def test_browser_is_default_backend(self) -> None:
        args = _build_parser().parse_args(
            ["--goal", "improve browser", "--branch", "side/1.0.01-test"]
        )
        self.assertEqual(args.backend, "browser")

    def test_api_backend_remains_explicit_fallback(self) -> None:
        args = _build_parser().parse_args(
            [
                "--goal",
                "improve browser",
                "--branch",
                "side/1.0.01-test",
                "--backend",
                "api",
            ]
        )
        self.assertEqual(args.backend, "api")


if __name__ == "__main__":
    unittest.main()
