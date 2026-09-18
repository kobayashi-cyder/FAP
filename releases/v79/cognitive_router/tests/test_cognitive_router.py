from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_cognitive_router import (
    CognitiveOrchestrator,
    CognitiveRouter,
    CognitiveRuntime,
    Critic,
    DistillationStore,
    NoRouteError,
    Planner,
    SkillExecutionError,
    SkillRegistry,
    SkillResult,
    TaskRequest,
    WorkingMemory,
    make_skill,
)


class CognitiveRouterTests(unittest.TestCase):
    def test_simple_chat_prefers_fast_local_skill(self):
        reg = SkillRegistry()
        reg.register(make_skill("local_chat", {"chat"}, lambda r, c: "local", quality=.78, avg_latency_ms=3, resource_cost=.02))
        reg.register(make_skill("remote_chat", {"chat"}, lambda r, c: "remote", quality=.99, avg_latency_ms=800, resource_cost=.8, online=True))
        decision, plan = CognitiveRouter(reg).route(TaskRequest("こんにちは", latency_budget_ms=20))
        self.assertEqual(decision.primary, "local_chat")
        self.assertIn("chat", plan.inferred_capabilities)

    def test_image_routes_to_image_capability(self):
        reg = SkillRegistry()
        reg.register(make_skill("chat", {"chat"}, lambda r, c: "x"))
        reg.register(make_skill("image", {"image"}, lambda r, c: SkillResult.success(b"png", confidence=.9)))
        decision, _ = CognitiveRouter(reg).route(TaskRequest("猫の画像を生成して"))
        self.assertEqual(decision.primary, "image")

    def test_online_disallowed_filters_online_skill(self):
        reg = SkillRegistry()
        reg.register(make_skill("local_web_cache", {"web"}, lambda r, c: "cached", quality=.55))
        reg.register(make_skill("live_web", {"web"}, lambda r, c: "live", quality=.99, online=True))
        decision, _ = CognitiveRouter(reg).route(TaskRequest("最新ニュースを検索", online_allowed=False))
        self.assertEqual(decision.primary, "local_web_cache")

    def test_no_route_is_explicit(self):
        reg = SkillRegistry()
        reg.register(make_skill("chat", {"chat"}, lambda r, c: "x"))
        with self.assertRaises(NoRouteError):
            CognitiveRouter(reg).route(TaskRequest("画像を作って", online_allowed=False))

    def test_planner_decomposes_multi_step_request(self):
        plan = Planner().plan(TaskRequest("設計して。そして実装して。次にテストして。"))
        self.assertGreaterEqual(len(plan.steps), 3)
        self.assertIn("planning", plan.inferred_capabilities)
        self.assertIn("code", plan.inferred_capabilities)

    def test_runtime_falls_back_after_exception(self):
        reg = SkillRegistry()
        def boom(r, c):
            raise RuntimeError("boom")
        reg.register(make_skill("a_bad", {"chat"}, boom, quality=.95, avg_latency_ms=1))
        reg.register(make_skill("b_good", {"chat"}, lambda r, c: SkillResult.success("ok", confidence=.9), quality=.8, avg_latency_ms=2))
        outcome = CognitiveRuntime(CognitiveRouter(reg)).handle(TaskRequest("こんにちは", max_attempts=2))
        self.assertEqual(outcome.skill_name, "b_good")
        self.assertEqual(outcome.result.output, "ok")
        self.assertEqual(outcome.attempts, ("a_bad", "b_good"))

    def test_low_confidence_falls_back(self):
        reg = SkillRegistry()
        reg.register(make_skill("a_weak", {"chat"}, lambda r, c: SkillResult.success("weak", confidence=.2), quality=.95))
        reg.register(make_skill("b_strong", {"chat"}, lambda r, c: SkillResult.success("strong", confidence=.92), quality=.8))
        outcome = CognitiveRuntime(CognitiveRouter(reg), critic=Critic(min_confidence=.6)).handle(TaskRequest("こんにちは", max_attempts=2))
        self.assertEqual(outcome.skill_name, "b_strong")
        self.assertIn("low_confidence", outcome.critiques[0].reasons)

    def test_required_evidence_can_force_escalation(self):
        reg = SkillRegistry()
        reg.register(make_skill("a_local", {"deep_reasoning"}, lambda r, c: SkillResult.success("guess", confidence=.9), quality=.95))
        reg.register(make_skill("b_verified", {"deep_reasoning"}, lambda r, c: SkillResult.success("checked", confidence=.9, evidence=("source:1",)), quality=.8))
        request = TaskRequest(
            "なぜこうなるか分析して",
            required_capabilities=frozenset({"deep_reasoning"}),
            metadata={"require_evidence": True},
            max_attempts=2,
        )
        out = CognitiveRuntime(CognitiveRouter(reg)).handle(request)
        self.assertEqual(out.skill_name, "b_verified")

    def test_side_effect_skill_is_not_accepted_without_permission(self):
        reg = SkillRegistry()
        reg.register(make_skill("a_mutating", {"code"}, lambda r, c: SkillResult.success("done", confidence=.9), quality=.99, side_effect=True))
        reg.register(make_skill("b_readonly", {"code"}, lambda r, c: SkillResult.success("plan", confidence=.8), quality=.8))
        out = CognitiveRuntime(CognitiveRouter(reg)).handle(TaskRequest("コードを実装して", max_attempts=2))
        self.assertEqual(out.skill_name, "b_readonly")
        self.assertNotIn("a_mutating", out.attempts)

    def test_working_memory_is_bounded(self):
        mem = WorkingMemory(max_items=4, max_chars=80)
        for i in range(10):
            mem.add("x", f"{i}-" + ("abcdefghij" * 3))
        self.assertLessEqual(len(mem.recent(99)), 4)
        self.assertLessEqual(sum(len(x.text) for x in mem.recent(99)), 80)

    def test_distillation_promotes_stable_preference(self):
        d = DistillationStore(min_support=3, min_success_rate=.8)
        req = TaskRequest("こんにちは")
        sig = d.signature(req, frozenset({"chat"}))
        for _ in range(3):
            d.record(sig, "learned", True)
        self.assertEqual(d.preferred(sig)[0], "learned")

    def test_distilled_preference_can_break_close_tie(self):
        reg = SkillRegistry()
        reg.register(make_skill("alpha", {"chat"}, lambda r, c: "a", quality=.8, avg_latency_ms=10))
        reg.register(make_skill("beta", {"chat"}, lambda r, c: "b", quality=.8, avg_latency_ms=10))
        d = DistillationStore(min_support=3)
        router = CognitiveRouter(reg, distillation=d)
        req = TaskRequest("こんにちは")
        decision, _ = router.route(req)
        self.assertEqual(decision.primary, "alpha")  # deterministic lexical tie-break
        for _ in range(3):
            d.record(decision.signature, "beta", True)
        decision2, _ = router.route(req)
        self.assertEqual(decision2.primary, "beta")

    def test_distillation_state_persists(self):
        import tempfile
        d = DistillationStore(min_support=2)
        req = TaskRequest("こんにちは")
        sig = d.signature(req, frozenset({"chat"}))
        d.record(sig, "local", True)
        d.record(sig, "local", True)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "routes.json"
            d.save(path)
            loaded = DistillationStore.load(path)
        self.assertEqual(loaded.preferred(sig)[0], "local")

    def test_orchestrator_routes_each_subgoal(self):
        reg = SkillRegistry()
        reg.register(make_skill("planner", {"planning"}, lambda r, c: SkillResult.success("plan:" + r.text, confidence=.9)))
        reg.register(make_skill("coder", {"code"}, lambda r, c: SkillResult.success("code:" + r.text, confidence=.9)))
        runtime = CognitiveRuntime(CognitiveRouter(reg))
        out = CognitiveOrchestrator(runtime).handle(TaskRequest("設計して。そして実装して。"))
        self.assertEqual(len(out.steps), 2)
        self.assertEqual(out.steps[0].outcome.skill_name, "planner")
        self.assertEqual(out.steps[1].outcome.skill_name, "coder")
        self.assertEqual(len(out.outputs), 2)

    def test_all_rejected_raises_clear_error(self):
        reg = SkillRegistry()
        reg.register(make_skill("weak", {"chat"}, lambda r, c: SkillResult.success("x", confidence=.1)))
        with self.assertRaises(SkillExecutionError):
            CognitiveRuntime(CognitiveRouter(reg)).handle(TaskRequest("こんにちは", max_attempts=1))

    def test_routing_is_deterministic(self):
        reg = SkillRegistry()
        for name in ("c", "a", "b"):
            reg.register(make_skill(name, {"chat"}, lambda r, c: "x", quality=.7, avg_latency_ms=10))
        router = CognitiveRouter(reg)
        routes = [router.route(TaskRequest("こんにちは"))[0].primary for _ in range(20)]
        self.assertEqual(len(set(routes)), 1)


if __name__ == "__main__":
    unittest.main()
