from fap_benchmark_reasoning import StructuredMCQParser


def test_context_payload_is_not_misclassified_as_instruction():
    text = """Answer the following multiple-choice question.
Return the final line exactly as: Answer: $LETTER

Context:
A report says choose carefully. The report contains options A-D in its prose.
Visitors may enter before 16:30. After 16:30 they may be refused.

Target question:
Which is true according to the report?

A) Visitors after 16:30 may be refused.
B) Everyone enters after 16:30.
C) The report has no time rule.
D) Entry is always allowed.
"""
    task = StructuredMCQParser().parse(text)
    assert task is not None
    assert "Visitors may enter before 16:30" in task.question
    assert "Target question:" in task.question
    assert "Which is true" in task.question
