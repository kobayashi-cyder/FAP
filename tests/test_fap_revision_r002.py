import unittest

from fap_revision_r001 import Signal
from fap_revision_r002 import (
    Route,
    RouteOutcome,
    expand_plan,
    plan_routes,
    update_route_priors,
    verification_decision,
)


def routes():
    return [
        Route(
            "logic",
            ("multi_step", "deduction"),
            relevance=0.9,
            evidence=0.8,
            cost=0.4,
        ),
        Route(
            "math",
            ("multi_step", "numeric"),
            relevance=0.82,
            evidence=0.85,
            cost=0.45,
        ),
        Route(
            "critic",
            ("verification", "counterexample"),
            relevance=0.78,
            evidence=0.9,
            cost=0.35,
        ),
        Route(
            "retrieval",
            ("evidence", "facts"),
            relevance=0.7,
            evidence=0.88,
            cost=0.25,
        ),
        Route(
            "alternate",
            ("abduction", "counterexample"),
            relevance=0.68,
            evidence=0.7,
            cost=0.5,
        ),
    ]


class RevisionR002Tests(unittest.TestCase):
    def test_easy_task_starts_slightly_dense_but_sparse(self):
        plan = plan_routes(routes())
        self.assertEqual(len(plan.active), 2)
        self.assertEqual(len(plan.edges), 1)
        self.assertLess(len(plan.active), len(routes()))

    def test_harder_task_raises_route_cap(self):
        easy = plan_routes(routes())
        hard = plan_routes(
            routes(),
            [
                Signal("multi_step", 1.0, 8),
                Signal("verification", 1.0, 8),
            ],
            uncertainty=1.0,
            disagreement=True,
        )
        self.assertGreater(hard.route_cap, easy.route_cap)
        self.assertGreaterEqual(len(hard.active), len(easy.active))
        self.assertLessEqual(hard.route_cap, len(routes()))

    def test_signal_affinity_changes_route_order(self):
        plan = plan_routes(
            routes(),
            [Signal("verification", 1.0, 8)],
        )
        positions = {
            score.name: i
            for i, score in enumerate(plan.scores)
        }
        self.assertLess(positions["critic"], positions["alternate"])

    def test_diversity_keeps_duplicate_family_from_crowding(self):
        pool = [
            Route(
                "a",
                ("x", "y"),
                relevance=1.0,
                evidence=1.0,
                cost=0.1,
            ),
            Route(
                "b",
                ("x", "y"),
                relevance=0.99,
                evidence=1.0,
                cost=0.1,
            ),
            Route(
                "c",
                ("z",),
                relevance=0.93,
                evidence=1.0,
                cost=0.1,
            ),
        ]
        plan = plan_routes(pool)
        self.assertIn("c", plan.active)

    def test_low_confidence_expands_one_route(self):
        plan = plan_routes(
            routes(),
            [Signal("multi_step", 1.0, 8)],
            uncertainty=0.9,
        )
        expanded = expand_plan(
            plan,
            [RouteOutcome(plan.active[0], 0.4, True)],
        )
        self.assertGreater(len(expanded.active), len(plan.active))

    def test_confident_agreement_does_not_expand(self):
        plan = plan_routes(routes())
        outcomes = [
            RouteOutcome(name, 0.95, True)
            for name in plan.active
        ]
        self.assertEqual(expand_plan(plan, outcomes), plan)

    def test_disagreement_expands_more_aggressively(self):
        plan = plan_routes(
            routes(),
            [
                Signal("verification", 1.0, 8),
                Signal("multi_step", 1.0, 8),
            ],
            uncertainty=0.8,
            disagreement=True,
        )
        outcomes = [
            RouteOutcome(
                plan.active[0],
                0.9,
                True,
                useful=True,
            ),
            RouteOutcome(
                plan.active[1],
                0.9,
                True,
                useful=False,
                contradiction=True,
            ),
        ]
        expanded = expand_plan(plan, outcomes)
        self.assertGreater(len(expanded.active), len(plan.active))

    def test_counterexample_forces_expansion_when_capacity_exists(self):
        plan = plan_routes(
            routes(),
            [Signal("multi_step", 1.0, 8)],
            uncertainty=0.8,
        )
        outcomes = [
            RouteOutcome(name, 0.95, True)
            for name in plan.active
        ]
        expanded = expand_plan(
            plan,
            outcomes,
            counterexample=True,
        )
        self.assertGreater(len(expanded.active), len(plan.active))

    def test_verification_is_fail_closed_without_verified_evidence(self):
        decision = verification_decision(
            [RouteOutcome("logic", 0.99, False)]
        )
        self.assertEqual(decision.status, "unresolved")
        self.assertEqual(decision.verified_routes, 0)

    def test_only_verified_outcomes_update_priors(self):
        priors = {"logic": 0.5, "critic": 0.5}
        updated = update_route_priors(
            priors,
            [
                RouteOutcome(
                    "logic",
                    1.0,
                    True,
                    useful=True,
                ),
                RouteOutcome(
                    "critic",
                    0.0,
                    False,
                    useful=False,
                ),
            ],
        )
        self.assertGreater(updated["logic"], 0.5)
        self.assertEqual(updated["critic"], 0.5)

    def test_negative_verified_outcome_reduces_prior(self):
        updated = update_route_priors(
            {"logic": 0.7},
            [
                RouteOutcome(
                    "logic",
                    0.9,
                    True,
                    useful=False,
                    contradiction=True,
                )
            ],
        )
        self.assertLess(updated["logic"], 0.7)

    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(ValueError):
            plan_routes(
                [
                    Route("same"),
                    Route("same"),
                ]
            )

    def test_ties_are_deterministic(self):
        pool = [
            Route("b"),
            Route("a"),
            Route("c"),
        ]
        one = plan_routes(pool)
        two = plan_routes(pool)
        self.assertEqual(one.active, two.active)
        self.assertEqual(one.scores, two.scores)


if __name__ == "__main__":
    unittest.main()
