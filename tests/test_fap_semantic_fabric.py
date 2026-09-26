from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fap_interaction_fabric import (
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)
from fap_semantic_action_router import SemanticActionRouter
from fap_semantic_fabric import SemanticFabricBridge
from fap_code_generator import CodeGeneratorOrgan


class SemanticFabricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.router = SemanticActionRouter(cls.root)

    def test_code_and_repository_routes_are_declarative(self):
        code = self.router.match("Pythonコードを作って")
        self.assertIsNotNone(code)
        self.assertEqual(code["route"], "artifact_code_generate")

        inspect = self.router.match("リポジトリを解析して")
        self.assertIsNotNone(inspect)
        self.assertEqual(inspect["route"], "repository_inspect")

        modify = self.router.match("リポジトリを修正して")
        self.assertIsNotNone(modify)
        self.assertEqual(modify["route"], "repository_coding")

    def test_bridge_binds_route_to_arbitrary_endpoint(self):
        fabric = InteractionFabric()
        bridge = SemanticFabricBridge(self.router)
        endpoint = InteractionEndpoint(
            endpoint_id="custom_repo",
            channels=("chat",),
            probe=lambda request: 0.0,
            handler=lambda request, budget: {"reply": "custom"},
        )
        fabric.register(
            bridge.bind(endpoint, ("repository_inspect",))
        )
        result = fabric.dispatch(
            InteractionRequest("リポジトリを解析して")
        )
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "custom_repo")
        self.assertEqual(result.payload["reply"], "custom")

    def test_bridge_preserves_endpoint_metadata_and_adds_route_capability(self):
        bridge = SemanticFabricBridge(self.router)
        endpoint = InteractionEndpoint(
            endpoint_id="metadata_repo",
            channels=("chat",),
            probe=lambda request: 0.0,
            handler=lambda request, budget: {"reply": "ok"},
            capabilities=("read_only",),
            task_families=("coding",),
            task_forms=("inspection",),
            failure_specialties=("retrieval",),
        )
        bound = bridge.bind(endpoint, ("repository_inspect",))
        self.assertIn("read_only", bound.capabilities)
        self.assertIn("repository_inspect", bound.capabilities)
        self.assertEqual(bound.task_families, ("coding",))
        self.assertEqual(bound.task_forms, ("inspection",))
        self.assertEqual(bound.failure_specialties, ("retrieval",))

    def test_unrelated_semantic_route_does_not_claim_request(self):
        fabric = InteractionFabric()
        bridge = SemanticFabricBridge(self.router)
        fabric.register(
            bridge.bind(
                InteractionEndpoint(
                    endpoint_id="repo_only",
                    channels=("chat",),
                    probe=lambda request: 1.0,
                    handler=lambda request, budget: {"reply": "repo"},
                ),
                ("repository_inspect",),
            )
        )
        result = fabric.dispatch(
            InteractionRequest("猫の画像を生成して")
        )
        self.assertEqual(result.state, "unhandled")

    def test_code_generator_accepts_adaptive_repair_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gen = CodeGeneratorOrgan(
                root / "artifacts",
                root / "workspace",
            )
            result = gen.build(
                "Pythonで四則演算できる電卓を作って。",
                max_repairs=0,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["repair_rounds"], 0)
            with self.assertRaises(ValueError):
                gen.build(
                    "Pythonで四則演算できる電卓を作って。",
                    max_repairs=5,
                )


if __name__ == "__main__":
    unittest.main()
