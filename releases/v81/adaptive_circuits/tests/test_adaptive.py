from __future__ import annotations

import unittest

from fap_adaptive_circuits import AdaptiveCircuitController, ActiveMemory


class AdaptiveCircuitTests(unittest.TestCase):
    def make_controller(self, top_k=2):
        c = AdaptiveCircuitController(top_k=top_k, memory_capacity=4)
        c.add_circuit("memory", tags=("記憶", "検索", "memory"), base_priority=0.20)
        c.add_circuit("verify", tags=("検証", "反例", "verifier"), base_priority=0.20)
        c.add_circuit("constraint", tags=("制約", "低RAM", "省メモリ"), base_priority=0.20)
        return c

    def certify(self, c, cid, score=1.0):
        return c.certify(cid, evidence_id=f"cert:{cid}", benchmark_score=score, static_checks=(True, True))

    def test_verifier_first_blocks_uncertified_circuits(self):
        c = self.make_controller()
        self.certify(c, "memory")
        decision = c.route("記憶を検索して検証する", top_k=3)
        self.assertEqual(decision.circuit_ids, ("memory",))

    def test_sparse_router_uses_only_top_k(self):
        c = self.make_controller(top_k=2)
        for cid in ("memory", "verify", "constraint"):
            self.certify(c, cid)
        decision = c.route("低RAMで記憶を検証する")
        self.assertEqual(len(decision.selected), 2)
        self.assertTrue(set(decision.circuit_ids) <= {"memory", "verify", "constraint"})

    def test_active_memory_is_success_only(self):
        c = self.make_controller()
        self.certify(c, "memory")
        decision = c.route("記憶を検索する", top_k=1)
        ok = c.observe(decision, evidence_id="out:fail", reward=0.95, success=False)
        self.assertFalse(ok)
        self.assertNotIn("memory", c.memory.entries)
        decision = c.route("記憶を検索する", top_k=1)
        ok = c.observe(decision, evidence_id="out:ok", reward=0.95, success=True)
        self.assertTrue(ok)
        self.assertIn("memory", c.memory.entries)

    def test_success_promotes_ephemeral_shadow_consolidated(self):
        c = self.make_controller()
        self.certify(c, "memory")
        stages = []
        for i in range(3):
            d = c.route("記憶を検索する", top_k=1)
            self.assertTrue(c.observe(d, evidence_id=f"success:{i}", reward=0.90, success=True))
            stages.append(c.registry.get("memory").stage)
        self.assertEqual(stages, ["ephemeral", "shadow", "consolidated"])

    def test_duplicate_verifier_evidence_is_rejected(self):
        c = self.make_controller()
        self.certify(c, "memory")
        d = c.route("記憶", top_k=1)
        c.observe(d, evidence_id="dup", reward=0.9, success=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            c.observe(d, evidence_id="dup", reward=0.9, success=True)

    def test_active_memory_boost_changes_future_priority(self):
        c = self.make_controller(top_k=1)
        for cid in ("memory", "verify"):
            self.certify(c, cid)
        d = c.route("検証", top_k=1)
        self.assertEqual(d.circuit_ids, ("verify",))
        for i in range(3):
            c.observe(d, evidence_id=f"boost:{i}", reward=1.0, success=True)
            d = c.route("検証", top_k=1)
        later = c.route("検証と記憶", top_k=1)
        self.assertEqual(later.circuit_ids, ("verify",))
        self.assertGreater(later.selected[0].memory_boost, 0.0)

    def test_evolution_children_are_unroutable_until_certified(self):
        c = self.make_controller(top_k=3)
        self.certify(c, "memory")
        for i in range(3):
            d = c.route("記憶", top_k=1)
            c.observe(d, evidence_id=f"evo:{i}", reward=0.95, success=True)
        children = c.evolve("memory", count=2)
        self.assertEqual(len(children), 2)
        self.assertTrue(all(x.stage == "candidate" and not x.verified for x in children))
        before = c.route("記憶", top_k=3)
        self.assertTrue(all(".g1." not in cid for cid in before.circuit_ids))
        child = children[0]
        c.certify(child.circuit_id, evidence_id="cert:child", benchmark_score=0.90, static_checks=(True,))
        after = c.route("記憶", top_k=3)
        self.assertIn(child.circuit_id, after.circuit_ids)

    def test_repeated_failure_quarantines_and_revokes(self):
        c = self.make_controller(top_k=1)
        self.certify(c, "memory")
        for i in range(3):
            d = c.route("記憶", top_k=1)
            self.assertEqual(d.circuit_ids, ("memory",))
            c.observe(d, evidence_id=f"bad:{i}", reward=0.1, success=False)
        spec = c.registry.get("memory")
        self.assertTrue(spec.quarantined)
        self.assertFalse(spec.verified)
        self.assertEqual(c.route("記憶", top_k=1).circuit_ids, ())

    def test_memory_capacity_is_bounded(self):
        m = ActiveMemory(capacity=2)
        m.observe_success("a", "alpha", 0.8)
        m.observe_success("b", "beta", 0.9)
        m.observe_success("c", "gamma", 1.0)
        self.assertEqual(len(m.entries), 2)
        self.assertIn("c", m.entries)

    def test_routing_is_deterministic(self):
        c = self.make_controller(top_k=2)
        for cid in ("memory", "verify", "constraint"):
            self.certify(c, cid)
        a = c.route("低RAMで記憶を検証")
        b = c.route("低RAMで記憶を検証")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
