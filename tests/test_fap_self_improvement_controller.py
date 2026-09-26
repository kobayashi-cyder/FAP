from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_repository_planner import PatchPlan, PlannedFile, RepositoryTask
from fap_repository_reader import RepositoryReadContext, SourceSlice
from fap_self_improvement_controller import (
    ChatGPTUILauncher,
    OpenAIRepositoryProposalProvider,
    OpenAIResponsesClient,
    SelfImprovementController,
    _extract_output_text,
)


class ResponsesClientTests(unittest.TestCase):
    def test_web_search_payload_and_output(self) -> None:
        seen = {}

        def transport(endpoint, headers, body, timeout, max_bytes):
            seen["endpoint"] = endpoint
            seen["headers"] = dict(headers)
            seen["payload"] = json.loads(body.decode("utf-8"))
            return json.dumps(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "research result",
                                    "annotations": [
                                        {
                                            "type": "url_citation",
                                            "url": "https://example.com/source",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ).encode("utf-8")

        client = OpenAIResponsesClient(
            api_key="test-key",
            model="test-model",
            transport=transport,
        )
        result = client.respond("inspect", web_search=True)
        self.assertEqual(result.text, "research result")
        self.assertTrue(result.used_web_search)
        self.assertIn("https://example.com/source", result.sources)
        self.assertEqual(
            seen["payload"]["tools"],
            [{"type": "web_search"}],
        )
        self.assertEqual(
            seen["headers"]["Authorization"],
            "Bearer test-key",
        )

    def test_extract_output_text_direct(self) -> None:
        self.assertEqual(
            _extract_output_text({"output_text": "ok"}),
            "ok",
        )


class LauncherTests(unittest.TestCase):
    def test_launcher_requires_explicit_enable(self) -> None:
        opened = []
        launcher = ChatGPTUILauncher(
            enabled=False,
            opener=lambda url: opened.append(url) or True,
        )
        self.assertFalse(launcher.launch())
        self.assertEqual(opened, [])

    def test_launcher_opens_chatgpt_when_enabled(self) -> None:
        opened = []
        launcher = ChatGPTUILauncher(
            enabled=True,
            opener=lambda url: opened.append(url) or True,
        )
        self.assertTrue(launcher.launch())
        self.assertEqual(opened, ["https://chatgpt.com/"])


class ProposalProviderTests(unittest.TestCase):
    def _plan(self) -> PatchPlan:
        return PatchPlan(
            version="fap.repository.plan.v1",
            plan_id="a" * 64,
            status="ready",
            task=RepositoryTask(
                goal="modify sample.py",
                repository_digest="b" * 64,
                max_files=8,
                max_source_bytes=120000,
            ),
            files=(
                PlannedFile(
                    path="sample.py",
                    before_sha256="c" * 64,
                    operation="modify",
                    reason="explicit",
                ),
            ),
            required_checks=("python_compile",),
            risk_flags=(),
            write_enabled=False,
        )

    def _context(self) -> RepositoryReadContext:
        return RepositoryReadContext(
            goal="modify sample.py",
            repository_digest="b" * 64,
            files=(
                SourceSlice(
                    path="sample.py",
                    language="python",
                    sha256="c" * 64,
                    score=10.0,
                    reasons=("exact_path",),
                    excerpt="VALUE = 1\n",
                    excerpt_bytes=10,
                ),
            ),
            omitted_files=0,
            index_errors=(),
        )

    def test_provider_returns_bounded_edit(self) -> None:
        def transport(endpoint, headers, body, timeout, max_bytes):
            return json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "edits": [
                                {
                                    "path": "sample.py",
                                    "operation": "modify",
                                    "content": "VALUE = 2\n",
                                }
                            ]
                        }
                    )
                }
            ).encode("utf-8")

        client = OpenAIResponsesClient(
            api_key="test-key",
            model="test-model",
            transport=transport,
        )
        provider = OpenAIRepositoryProposalProvider(
            client,
            use_web_search=False,
        )
        edits = tuple(provider(self._plan(), self._context()))
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0].path, "sample.py")
        self.assertEqual(edits[0].before_sha256, "c" * 64)
        self.assertEqual(edits[0].content, "VALUE = 2\n")

    def test_provider_rejects_path_outside_plan(self) -> None:
        def transport(endpoint, headers, body, timeout, max_bytes):
            return json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "edits": [
                                {
                                    "path": ".github/workflows/disable.yml",
                                    "operation": "modify",
                                    "content": "disabled\n",
                                }
                            ]
                        }
                    )
                }
            ).encode("utf-8")

        client = OpenAIResponsesClient(
            api_key="test-key",
            model="test-model",
            transport=transport,
        )
        provider = OpenAIRepositoryProposalProvider(
            client,
            use_web_search=False,
        )
        with self.assertRaisesRegex(ValueError, "outside plan"):
            tuple(provider(self._plan(), self._context()))


class ControllerGuardTests(unittest.TestCase):
    def test_main_branch_is_never_self_modified(self) -> None:
        class FakeClient:
            def respond(self, *args, **kwargs):
                raise AssertionError("reasoner must not be called")

        class FakeOrchestrator:
            def prepare(self, *args, **kwargs):
                raise AssertionError("orchestrator must not be called")

        with tempfile.TemporaryDirectory() as tmp:
            controller = SelfImprovementController(
                Path(tmp),
                client=FakeClient(),
                orchestrator=FakeOrchestrator(),
            )
            with self.assertRaisesRegex(ValueError, "non-main"):
                controller.run("improve tests", branch="main")


if __name__ == "__main__":
    unittest.main()
