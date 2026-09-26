from __future__ import annotations

import re

import fap_v87_12_semantic_adaptive_gateway as v12
import fap_v87_25_structured_reasoning_gateway as gateway
from fap_benchmark_reasoning import StructuredMCQParser, StructuredMCQReasoner, StructuredMCQVerifier


GPQA_STYLE = """Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before answering.

In a quantum field experiment, which statement best describes the electron state over time?

A) It is always a classical particle
B) It can be represented by a quantum state evolving in time
C) Weather determines the wavefunction
D) Create a new date every second
"""


def test_parser_separates_instruction_question_and_domain():
    task = StructuredMCQParser().parse(GPQA_STYLE)
    assert task is not None
    assert "Answer the following" in task.instruction
    assert task.question.startswith("In a quantum field experiment")
    assert list(task.choices) == ["A", "B", "C", "D"]
    assert task.domain == "physics"


def test_normal_abcd_list_without_answer_contract_is_not_hijacked():
    text = """買い物候補です。
A) りんご
B) みかん
C) バナナ
D) ぶどう
"""
    assert StructuredMCQParser().parse(text) is None


def test_verified_literal_arithmetic_mcq():
    text = """Answer the following multiple choice question.
What is 2 + 2?

A) 3
B) 4
C) 5
D) 6
"""
    task = StructuredMCQParser().parse(text)
    assert task is not None
    reasoner = StructuredMCQReasoner()
    result = reasoner.run(task)
    assert result["decision_source"] == "verified_arithmetic"
    assert result["reply"].splitlines()[-1] == "Answer: $B"
    verdict, _ = StructuredMCQVerifier().verify(task, result)
    assert verdict == "OK"


def test_unresolved_fallback_is_semantic_content_stable_across_reordering():
    p1 = """Answer the following multiple choice question.
Which unknown proposition is correct?

A) alpha option
B) beta option
C) gamma option
D) delta option
"""
    p2 = """Answer the following multiple choice question.
Which unknown proposition is correct?

A) gamma option
B) alpha option
C) delta option
D) beta option
"""
    parser = StructuredMCQParser()
    reasoner = StructuredMCQReasoner()
    t1 = parser.parse(p1)
    t2 = parser.parse(p2)
    assert t1 is not None and t2 is not None
    d1 = reasoner.decide(t1)
    d2 = reasoner.decide(t2)
    assert d1.source == "unresolved_content_tiebreak"
    assert d2.source == "unresolved_content_tiebreak"
    assert t1.choices[d1.letter] == t2.choices[d2.letter]


def test_gpqa_keywords_are_shielded_from_legacy_router(monkeypatch, tmp_path):
    class Memory:
        def __init__(self):
            self.rows = {}

        def load(self, sid):
            return list(self.rows.get(sid, []))

        def append(self, sid, role, text, meta=None):
            self.rows.setdefault(sid, []).append({"role": role, "text": text, "meta": meta or {}})

    monkeypatch.setattr(gateway.base, "MEMORY", Memory())
    monkeypatch.setattr(gateway.base, "EVAL_LOG", tmp_path / "eval.jsonl")

    core = gateway.FAPV8725()
    monkeypatch.setattr(core, "status", lambda: {"version": gateway.VERSION})
    result = core.chat(GPQA_STYLE, "gpqa-shield")

    assert result["ability"] == "structured_mcq"
    assert result["route"][0] == "structured-detect"
    assert re.fullmatch(r"Answer: \$[A-D]", result["reply"].splitlines()[-1])
    assert result["verdict"] in {"OK", "PARTIAL"}


def test_non_mcq_delegates_to_inherited_v8712_unchanged(monkeypatch):
    sentinel = {"reply": "legacy", "ability": "weather"}

    def legacy_chat(self, text, sid):
        return sentinel

    monkeypatch.setattr(v12.FAPV8712, "chat", legacy_chat)
    core = gateway.FAPV8725()
    assert core.chat("米子市の今日の天気は？", "legacy") is sentinel
