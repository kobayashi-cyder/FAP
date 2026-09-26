from __future__ import annotations

import unittest

from fap_dynamic_sparse_routing import (
    DynamicSparseConfig,
    DynamicSparseRouter,
    RouteSpec,
    RoutingContext,
    RoutingFeedback,
)


def routes():
    return (
        RouteSpec(
            "reader",
            capabilities=("retrieval", "evidence"),
            task_families=("language", "social"),
            task_forms=("reading",),
            failure_specialties=("evidence_selection",),
            prior_quality=0.62,
            cost=1.0,
        ),
        RouteSpec(
            "symbolic",
            capabilities=("algebra", "logic"),
            task_families=("math", "science"),
            task_forms=("symbolic", "multi_step"),
            failure_specialties=("decomposition", "logic"),
            prior_quality=0.64,
            cost=1.2,
        ),
        RouteSpec(
            "numeric",
            capabilities=("arithmetic", "numeric"),
            task_families=("math", "science"),
            task_forms=("numeric", "multi_step"),
            failure_specialties=("arithmetic",),
            prior_quality=0.61,
            cost=0.9,
        ),
        RouteSpec(
            "verifier",
            capabilities=("verification", "counterexample"),
            task_families=("math", "science", "language", "social"),
            task_forms=("multi_step", "reading", "numeric", "symbolic"),
            failure_specialties=("verification",),
            prior_quality=0.58,
            cost=1.1,
        ),
        RouteSpec(
            "decomposer",
            capabilities=("decomposition", "planning"),
            task_families=("math", "science", "language"),
            task_forms=("multi_step",),
            failure_specialties=("decomposition",),
            prior_quality=0.57,
            cost=1.0,
        ),
        RouteSpec(
            "fallback",
            capabilities=("general",),
            task_families=("language", "math", "science", "social"),
            task_forms=("reading", "numeric", "symbolic", "multi_step"),
            failure_specialties=("unknown",),
            prior_quality=0.50,
            cost=0.8,
        ),
    )


class DynamicSparseRoutingTests(unittest.TestCase):
    def test_initial_graph_is_slightly_dense_and_connected_outward(self):
        router = DynamicSparseRouter(routes(), seed="test")
        self.assertGreater(router.density, 0.20)
        self.assertLess(router.density, 0.70)
        for route_id in router.routes:
            outgoing = [
                edge
                for edge in router.edges.values()
                if edge.source == route_id and edge.active
            ]
            self.assertGreaterEqual(len(outgoing), 1)

    def test_math_numeric_context_prefers_specialized_route(self):
        router = DynamicSparseRouter(routes(), seed="test")
        decision = router.select(
            RoutingContext(
                task_family="math",
                task_form="numeric",
                required_capabilities=("arithmetic", "numeric"),
            ),
            top_k=3,
        )
        ids = [item.route_id for item in decision.selected]
        self.assertIn("numeric", ids[:2])

    def test_warmup_then_successful_route_becomes_more_preferred(self):
        config = DynamicSparseConfig(warmup_steps=2)
        router = DynamicSparseRouter(routes(), config=config, seed="learn")
        context = RoutingContext(
            task_family="math",
            task_form="numeric",
            required_capabilities=("arithmetic",),
        )
        before = {
            item.route_id: item.final_score
            for item in router.select(context, top_k=6).selected
        }
        for _ in range(8):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=("fallback", "numeric"),
                    successful_route_id="numeric",
                    reward=0.95,
                    verified=True,
                    context=context,
                )
            )
        after = {
            item.route_id: item.final_score
            for item in router.select(context, top_k=6).selected
        }
        self.assertGreater(after["numeric"], before["numeric"])
        self.assertGreater(
            router.state["numeric"].utility_ema,
            router.state["fallback"].utility_ema,
        )

    def test_easy_repeated_work_sparsifies_after_warmup(self):
        config = DynamicSparseConfig(warmup_steps=1)
        router = DynamicSparseRouter(routes(), config=config, seed="sparse")
        initial_density = router.density
        context = RoutingContext(
            task_family="language",
            task_form="reading",
            required_capabilities=("retrieval",),
            uncertainty=0.05,
            novelty=0.05,
        )
        for _ in range(10):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=("reader", "verifier"),
                    successful_route_id="reader",
                    reward=0.92,
                    verified=True,
                    context=context,
                )
            )
        router.select(context)
        self.assertLess(router.density, initial_density)
        self.assertGreaterEqual(router.density, config.sparse_floor - 0.05)

    def test_uncertainty_and_novelty_can_reactivate_edges(self):
        config = DynamicSparseConfig(
            warmup_steps=0,
            sparse_floor=0.10,
            sparse_target=0.12,
            initial_density=0.38,
            reactivation_budget=6,
        )
        router = DynamicSparseRouter(routes(), config=config, seed="reactivate")
        easy = RoutingContext(
            task_family="language",
            task_form="reading",
            uncertainty=0.0,
            novelty=0.0,
        )
        for _ in range(8):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=("reader",),
                    successful_route_id="reader",
                    reward=0.9,
                    verified=True,
                    context=easy,
                )
            )
        router.select(easy)
        sparse_edges = router.active_edges

        hard = RoutingContext(
            task_family="science",
            task_form="multi_step",
            required_capabilities=("logic", "verification"),
            failure_classes=("decomposition", "verification"),
            uncertainty=0.95,
            novelty=0.90,
            verifier_disagreement=0.85,
        )
        decision = router.select(hard)
        self.assertTrue(decision.densified or router.active_edges > sparse_edges)
        self.assertGreaterEqual(router.active_edges, sparse_edges)

    def test_failure_reduces_used_edge_and_opens_exploration(self):
        router = DynamicSparseRouter(routes(), seed="failure")
        context = RoutingContext(
            task_family="math",
            task_form="multi_step",
            failure_classes=("verification",),
            uncertainty=0.8,
        )
        edge = router.edges[("symbolic", "verifier")]
        edge.active = True
        before = edge.weight
        router.observe(
            RoutingFeedback(
                selected_route_ids=("symbolic", "verifier"),
                reward=0.1,
                verified=False,
                context=context,
            )
        )
        self.assertLess(edge.weight, before)
        self.assertGreaterEqual(router.density, router.config.sparse_floor)

    def test_high_risk_path_prefers_verification_coverage(self):
        router = DynamicSparseRouter(
            routes(),
            config=DynamicSparseConfig(
                warmup_steps=0,
                reactivation_budget=8,
            ),
            seed="path",
        )
        decision = router.select(
            RoutingContext(
                task_family="science",
                task_form="multi_step",
                required_capabilities=("logic", "verification"),
                failure_classes=("decomposition", "verification"),
                uncertainty=0.95,
                novelty=0.85,
                verifier_disagreement=0.95,
            ),
            top_k=4,
        )
        self.assertGreaterEqual(len(decision.primary_path.route_ids), 2)
        self.assertTrue(decision.primary_path.verification_covered)
        self.assertTrue(decision.primary_path.failure_specialty_covered)
        for source, target in zip(
            decision.primary_path.route_ids,
            decision.primary_path.route_ids[1:],
        ):
            self.assertTrue(router.edges[(source, target)].active)

    def test_learning_state_round_trip_preserves_generic_router_state(self):
        router = DynamicSparseRouter(routes(), seed="persist")
        context = RoutingContext(
            task_family="math",
            task_form="numeric",
            required_capabilities=("arithmetic",),
        )
        for _ in range(4):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=("numeric", "verifier"),
                    successful_route_id="numeric",
                    reward=0.93,
                    verified=True,
                    latency=0.4,
                    context=context,
                )
            )
        payload = router.export_learning_state()

        restored = DynamicSparseRouter(routes(), seed="persist")
        restored.import_learning_state(payload)

        self.assertEqual(restored.step, router.step)
        self.assertEqual(restored.active_edges, router.active_edges)
        self.assertAlmostEqual(
            restored.state["numeric"].utility_ema,
            router.state["numeric"].utility_ema,
            places=9,
        )
        self.assertEqual(
            restored.select(context).primary_path.route_ids,
            router.select(context).primary_path.route_ids,
        )

    def test_feedback_rejects_winner_outside_selected_path(self):
        router = DynamicSparseRouter(routes(), seed="winner")
        with self.assertRaisesRegex(ValueError, "successful_route_id"):
            router.observe(
                RoutingFeedback(
                    selected_route_ids=("reader",),
                    successful_route_id="numeric",
                    reward=0.8,
                    verified=True,
                )
            )

    def test_tampered_learning_state_is_rejected(self):
        router = DynamicSparseRouter(routes(), seed="tamper")
        payload = router.export_learning_state()
        payload["step"] = 99
        with self.assertRaisesRegex(ValueError, "checksum"):
            router.import_learning_state(payload)

    def test_snapshot_contains_no_question_or_answer_memory(self):
        router = DynamicSparseRouter(routes(), seed="safe")
        snap = repr(router.snapshot()).casefold()
        self.assertNotIn("question_text", snap)
        self.assertNotIn("answer_key", snap)
        self.assertIn("density", snap)


if __name__ == "__main__":
    unittest.main()
