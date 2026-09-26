from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
V79_ROOT = ROOT.parents[1] / "v79" / "creativity_engine"
sys.path.insert(0, str(V79_ROOT))
sys.path.insert(0, str(ROOT))

from fap_self_curriculum import (
    AbilityMap,
    AttemptResult,
    CurriculumGenerator,
    CurriculumTask,
    PatternStore,
    SelfCurriculumEngine,
    SuccessCompressor,
    VerificationResult,
    build_primitive_self_curriculum,
    build_v84_curriculum,
)


class V84SelfCurriculumTests(unittest.TestCase):
    def test_success_is_compressed_but_failure_is_not(self):
        def solver(task, priors):
            ok = task.ability == "composition"
            answer = (
                "reusable verified composition structure"
                if ok
                else "failed exploration trace"
            )
            return AttemptResult(
                answer,
                {"sandbox": task.task_id},
            )

        def verifier(task, attempt):
            ok = "verified" in attempt.answer
            return VerificationResult(
                ok,
                0.94 if ok else 0.15,
                "independent sandbox",
                independent=True,
            )

        engine = SelfCurriculumEngine(
            ["composition", "generalization"],
            solver=solver,
            verifier=verifier,
        )
        events = engine.run(6)
        self.assertTrue(
            any(
                e["stored_success_pattern"]
                for e in events
            )
        )
        self.assertTrue(
            all(
                not e["stored_success_pattern"]
                for e in events
                if e["task"]["ability"]
                == "generalization"
            )
        )
        self.assertGreater(
            engine.ability_map.snapshot()[
                "composition"
            ]["frontier"],
            0.25,
        )

    def test_non_independent_success_does_not_enter_memory(self):
        task = CurriculumTask(
            "t1",
            "verification",
            "verify x",
            0.4,
        )
        attempt = AttemptResult(
            "verified-looking answer",
            {"same_solver": True},
        )
        verification = VerificationResult(
            True,
            1.0,
            "self assertion",
            independent=False,
        )
        with self.assertRaises(ValueError):
            SuccessCompressor().compress(
                task,
                attempt,
                verification,
            )

    def test_non_independent_success_does_not_advance_ability_frontier(self):
        amap = AbilityMap(["verification"])
        before = amap.snapshot()["verification"]
        amap.update(
            "verification",
            0.8,
            VerificationResult(
                True,
                1.0,
                "self assertion",
                independent=False,
            ),
        )
        after = amap.snapshot()["verification"]
        self.assertEqual(after["successes"], 0)
        self.assertEqual(after["frontier"], before["frontier"])
        self.assertLess(after["ema_reward"], before["ema_reward"])

    def test_evidence_digest_is_bound_to_full_challenge(self):
        compressor = SuccessCompressor()
        attempt = AttemptResult(
            "compose robust parser boundary guard",
            {"case": 1},
        )
        vr = VerificationResult(
            True,
            0.9,
            "holdout",
            independent=True,
        )
        first = compressor.compress(
            CurriculumTask(
                "same-task-id",
                "composition",
                "compose at difficulty 0.40",
                0.40,
                payload={"variant": "a"},
            ),
            attempt,
            vr,
        )
        second = compressor.compress(
            CurriculumTask(
                "same-task-id",
                "composition",
                "compose at difficulty 0.55",
                0.55,
                payload={"variant": "b"},
            ),
            attempt,
            vr,
        )
        self.assertNotEqual(
            first.evidence_digests[0],
            second.evidence_digests[0],
        )
        store = PatternStore()
        self.assertTrue(store.add(first))
        self.assertTrue(store.add(second))
        self.assertEqual(
            store.for_ability("composition")[0].stage,
            "shadow",
        )

    def test_generated_task_is_slightly_above_frontier(self):
        state = AbilityMap(
            ["repair"]
        ).states["repair"]
        task = CurriculumGenerator(
            stretch=0.10
        ).generate(state, [])
        self.assertGreater(
            task.difficulty,
            state.frontier,
        )
        self.assertLessEqual(
            task.difficulty,
            0.50,
        )

    def test_focus_does_not_starve_untried_ability(self):
        amap = AbilityMap(["a", "b"])
        fail = VerificationResult(
            False,
            0.0,
            "fail",
        )
        first = amap.choose_focus().ability
        amap.update(first, 0.4, fail)
        seen = {first}
        for _ in range(4):
            nxt = amap.choose_focus().ability
            seen.add(nxt)
            amap.update(nxt, 0.4, fail)
        self.assertEqual(seen, {"a", "b"})

    def test_ability_map_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ability-map.json"
            amap = AbilityMap(
                ["composition"],
                path,
            )
            amap.update(
                "composition",
                0.6,
                VerificationResult(
                    True,
                    0.95,
                    "holdout",
                ),
            )
            before = amap.snapshot()["composition"]
            loaded = AbilityMap(
                ["composition"],
                path,
            )
            after = loaded.snapshot()["composition"]
            self.assertEqual(
                after["attempts"],
                before["attempts"],
            )
            self.assertEqual(
                after["successes"],
                before["successes"],
            )
            self.assertEqual(
                after["frontier"],
                before["frontier"],
            )

    def test_pattern_store_persists_only_compressed_record(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "patterns.json"
            store = PatternStore(path)
            task = CurriculumTask(
                "t2",
                "repair",
                "repair parser",
                0.5,
            )
            attempt = AttemptResult(
                "parser boundary guard retry",
                {"case": 7},
            )
            vr = VerificationResult(
                True,
                0.9,
                "holdout",
                independent=True,
            )
            pattern = SuccessCompressor().compress(
                task,
                attempt,
                vr,
            )
            self.assertTrue(store.add(pattern))
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
            )
            self.assertNotIn(
                attempt.answer,
                encoded,
            )
            reloaded = PatternStore(path)
            self.assertEqual(
                len(
                    reloaded.for_ability(
                        "repair"
                    )
                ),
                1,
            )
            self.assertEqual(
                reloaded.for_ability(
                    "repair"
                )[0].stage,
                "ephemeral",
            )

    def test_repeated_independent_success_promotes_pattern(self):
        store = PatternStore()
        compressor = SuccessCompressor()
        for i in range(3):
            task = CurriculumTask(
                f"p{i}",
                "composition",
                "compose robust parser",
                0.5 + 0.05 * i,
            )
            attempt = AttemptResult(
                "compose robust parser boundary guard",
                {"case": i},
            )
            vr = VerificationResult(
                True,
                0.9,
                f"holdout-{i}",
                independent=True,
            )
            self.assertTrue(
                store.add(
                    compressor.compress(
                        task,
                        attempt,
                        vr,
                    )
                )
            )
        patterns = store.for_ability(
            "composition"
        )
        self.assertEqual(
            len(patterns),
            1,
        )
        self.assertEqual(
            patterns[0].stage,
            "consolidated",
        )
        self.assertEqual(
            len(patterns[0].evidence_digests),
            3,
        )

    def test_solver_exception_becomes_learning_failure_not_crash(self):
        def solver(task, priors):
            raise RuntimeError("cannot solve yet")

        def verifier(task, attempt):
            self.fail(
                "verifier should not run "
                "after solver error"
            )

        engine = SelfCurriculumEngine(
            ["repair"],
            solver=solver,
            verifier=verifier,
        )
        event = engine.step()
        self.assertFalse(
            event["verification"]["passed"]
        )
        self.assertEqual(
            event["verification"]["reason"],
            "solver_error:RuntimeError",
        )
        self.assertEqual(
            engine.ability_map.snapshot()[
                "repair"
            ]["attempts"],
            1,
        )

    def test_generic_facade_exposes_capability_map(self):
        def solver(task, priors):
            return AttemptResult(
                "ok verified reusable",
                {"id": task.task_id},
            )

        def verifier(task, attempt):
            return VerificationResult(
                True,
                0.9,
                "sandbox holdout",
                independent=True,
            )

        with tempfile.TemporaryDirectory() as td:
            fap = build_v84_curriculum(
                solver=solver,
                verifier=verifier,
                abilities=["composition"],
                ability_map_path=(
                    Path(td) / "abilities.json"
                ),
                store_path=(
                    Path(td) / "patterns.json"
                ),
            )
            out = fap.dream(2)
            self.assertEqual(len(out), 2)
            self.assertEqual(
                fap.capability_map()[
                    "composition"
                ]["successes"],
                2,
            )
            self.assertTrue(
                fap.compressed_successes(
                    "composition"
                )
            )

    def test_real_v80_primitive_sandbox_bridge(self):
        with tempfile.TemporaryDirectory() as td:
            fap = build_primitive_self_curriculum(
                ability_map_path=(
                    Path(td) / "abilities.json"
                ),
                pattern_store_path=(
                    Path(td) / "patterns.json"
                ),
                registry_path=(
                    Path(td) / "registry.json"
                ),
            )
            events = fap.dream(3)
            self.assertEqual(
                len(events),
                3,
            )
            self.assertTrue(
                all(
                    e["verification"]["passed"]
                    for e in events
                )
            )
            self.assertEqual(
                {
                    e["task"]["ability"]
                    for e in events
                },
                {
                    "string_normalization",
                    "numeric_transform",
                    "list_transform",
                },
            )
            self.assertEqual(
                sum(
                    x["successes"]
                    for x
                    in fap.capability_map().values()
                ),
                3,
            )
            self.assertGreaterEqual(
                len(fap.active_primitives()),
                3,
            )


if __name__ == "__main__":
    unittest.main()
