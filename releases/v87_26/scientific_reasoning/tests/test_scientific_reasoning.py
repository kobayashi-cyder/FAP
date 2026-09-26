from __future__ import annotations

import fap_v87_25_structured_reasoning_gateway as v25
from fap_benchmark_reasoning import StructuredMCQParser
from fap_scientific_reasoning import OptionConditionedScientificReasoner
import fap_v87_26_scientific_reasoning_gateway as gateway


def parse(text):
    task = StructuredMCQParser().parse(text)
    assert task is not None
    return task


def test_electron_fermion_rule_selects_content_not_letter():
    t = parse("""Answer the following multiple choice question.
Which particle is a fermion?

A) photon
B) electron
C) phonon
D) classical wave
""")
    r = OptionConditionedScientificReasoner(gateway.CORE.mcq_reasoner).run(t)
    assert r["decision_source"] == "option_conditioned_science"
    assert r["reply"].splitlines()[-1] == "Answer: $B"


def test_negative_question_inverts_truth_selection():
    t = parse("""Answer the following multiple choice question.
Which statement is NOT correct?

A) Oxidation involves loss of electrons
B) Reduction involves gain of electrons
C) A catalyst lowers activation energy
D) Oxidation means gain of electrons
""")
    r = OptionConditionedScientificReasoner(gateway.CORE.mcq_reasoner).run(t)
    assert r["decision_source"] == "option_conditioned_science"
    assert r["reply"].splitlines()[-1] == "Answer: $D"


def test_uncertain_question_falls_back():
    t = parse("""Answer the following multiple choice question.
Which unknown proposition is correct?

A) alpha
B) beta
C) gamma
D) delta
""")
    r = OptionConditionedScientificReasoner(gateway.CORE.mcq_reasoner).run(t)
    assert r["decision_source"] == "unresolved_content_tiebreak"
    assert r["forced_choice"] is True


def test_non_mcq_delegates_to_v8725(monkeypatch):
    sentinel = {"reply": "legacy", "ability": "weather"}
    def old(self, text, sid):
        return sentinel
    monkeypatch.setattr(v25.FAPV8725, "chat", old)
    core = gateway.FAPV8726()
    assert core.chat("米子市の今日の天気は？", "x") is sentinel


def test_option_assessments_are_exposed(monkeypatch, tmp_path):
    class Mem:
        def load(self, sid): return []
        def append(self, *args, **kwargs): pass
    monkeypatch.setattr(gateway.base, "MEMORY", Mem())
    monkeypatch.setattr(gateway.base, "EVAL_LOG", tmp_path / "eval.jsonl")
    core = gateway.FAPV8726()
    monkeypatch.setattr(core, "status", lambda: {"version": gateway.VERSION})
    out = core.chat("""Answer the following multiple choice question.
Which particle is a fermion?

A) photon
B) electron
C) phonon
D) classical wave
""", "x")
    assert out["structured_mcq"]["decision_source"] == "option_conditioned_science"
    assert len(out["structured_mcq"]["option_assessments"]) == 4
