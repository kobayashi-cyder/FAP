from __future__ import annotations

from fap_benchmark_reasoning import StructuredMCQParser
from fap_physics_knowledge import PhysicsKnowledgeReasoner, PhysicsKnowledgeStore, validate_knowledge_patterns
import fap_v87_26_scientific_reasoning_gateway as v26
import fap_v87_27_physics_knowledge_gateway as gateway


def parse(s):
    t = StructuredMCQParser().parse(s)
    assert t is not None
    return t


def test_all_knowledge_patterns_compile():
    assert validate_knowledge_patterns() == []


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
    assert r["reply"].splitlines()[-1] == "Answer: $B"
    assert r["physics_knowledge"]["advisory_only"] is True
    assert r["physics_knowledge"]["used"] is False



def test_stem_fact_does_not_leak_equal_evidence_to_all_options():
    t = parse("""Answer the following multiple choice question.
For photons, E = hc/lambda. Which conclusion is correct?

A) Shorter wavelength means higher photon energy
B) Longer wavelength means higher photon energy
C) Photon energy is independent of wavelength
D) Every wavelength has zero energy
""")
    rows, retrieved = PhysicsKnowledgeStore().evaluate_options(t)
    scores = {x.letter: x.score for x in rows}
    assert retrieved
    assert scores["A"] > scores["B"]
    assert len(set(scores.values())) > 1


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


def test_numeric_solver_photon_energy():
    t = parse("""Answer the following multiple choice question.
A photon has wavelength 620 nm. What is its energy?

A) 0.50 eV
B) 2.00 eV
C) 5.00 eV
D) 20.0 eV
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_numeric_solver"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_numeric_solver_lorentz_gamma():
    t = parse("""Answer the following multiple choice question.
A spacecraft moves at speed 0.8 c. What is its Lorentz factor gamma?

A) 1.25
B) 1.67
C) 2.50
D) 5.00
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_numeric_solver"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_numeric_solver_hubble_law():
    t = parse("""Answer the following multiple choice question.
Using a Hubble constant H0 = 70 km/s/Mpc, what recession velocity corresponds to a distance of 100 Mpc?

A) 700 km/s
B) 7000 km/s
C) 70000 km/s
D) 70 km/s
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_numeric_solver"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_numeric_solver_schwarzschild_radius():
    t = parse("""Answer the following multiple choice question.
What is the Schwarzschild radius of a black hole with mass 10 solar masses?

A) 2.95 km
B) 29.5 km
C) 295 km
D) 2950 km
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_numeric_solver"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_numeric_solver_classical_kinetic_energy():
    t = parse("""Answer the following multiple choice question.
An object has mass = 2 kg and speed = 3 m/s. What is its kinetic energy?

A) 3 J
B) 6 J
C) 9 J
D) 18 J
""")
    r = PhysicsKnowledgeReasoner(gateway.CORE.science_reasoner).run(t)
    assert r["decision_source"] == "physics_numeric_solver"
    assert r["reply"].splitlines()[-1] == "Answer: $C"
