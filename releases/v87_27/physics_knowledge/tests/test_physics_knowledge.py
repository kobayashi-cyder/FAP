from __future__ import annotations

from fap_benchmark_reasoning import StructuredMCQParser
from fap_physics_knowledge import PhysicsKnowledgeReasoner, PhysicsKnowledgeStore
import fap_v87_26_scientific_reasoning_gateway as v26
import fap_v87_27_physics_knowledge_gateway as gateway


def parse(s):
    t = StructuredMCQParser().parse(s)
    assert t is not None
    return t


def test_store_has_broad_physics_areas():
    s = PhysicsKnowledgeStore.stats()
    assert s["entries"] >= 35
    for area in ["quantum","particle","mechanics","electromagnetism","thermodynamics","relativity"]:
        assert s["areas"].get(area, 0) >= 1
    assert s["benchmark_answer_keys"] == 0


def test_retrieval_selects_uncertainty_knowledge():
    t = parse("""Answer the following multiple choice question.
Which statement about position and momentum is correct in quantum mechanics?

A) They can always both be exact
B) Their uncertainties obey a lower bound
C) Momentum does not exist
D) Position is a classical probability
""")
    rows = PhysicsKnowledgeStore().retrieve(t)
    ids = [x.entry.knowledge_id for x in rows]
    assert "qm_uncertainty" in ids


def test_physics_reasoner_answers_electron_fermion():
    t = parse("""Answer the following multiple choice question.
Which statement about the electron is correct?

A) It is a spin-1 boson
B) It is a spin-1/2 fermion
C) It is a gluon
D) It has no quantum statistics
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_knowledge_retrieval"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_nonphysics_delegates_to_v8726_path():
    t = parse("""Answer the following multiple choice question.
Which statement about DNA is correct?

A) DNA can serve as a template for RNA transcription
B) DNA is a photon
C) DNA is an electric field
D) DNA is a heat engine
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["physics_knowledge"]["used"] is False


def test_normal_chat_delegates_to_v8726(monkeypatch):
    sentinel = {"reply":"legacy","ability":"weather"}
    def old(self, text, sid): return sentinel
    monkeypatch.setattr(v26.FAPV8726, "chat", old)
    core = gateway.FAPV8727()
    assert core.chat("米子市の今日の天気は？", "x") is sentinel
