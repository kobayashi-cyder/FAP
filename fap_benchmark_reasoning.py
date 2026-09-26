from __future__ import annotations

import ast
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_FULLWIDTH = str.maketrans({"Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D"})
_CHOICE_MARKER = re.compile(r"(?m)^[ \t]*([A-DＡ-Ｄ])[\)\].:：][ \t]*")
_ANSWER_RE = re.compile(r"(?i)Answer[ \t]*:[ \t]*\$?([A-D])\$?")
_CONTRACT_RE = re.compile(
    r"(?i)(multiple[ -]?choice|one of\s+ABCD|Answer\s*:|"
    r"last line.{0,80}Answer|choose.{0,30}[A-D]|"
    r"選択肢|四択|4択|A[\-/]B[\-/]C[\-/]D|A.?D.{0,20}(選|答))"
)
_GENERIC_INSTRUCTION = re.compile(
    r"(?i)^(answer the following multiple choice question|"
    r"the last line of your response should be|"
    r"think step by step before answering|"
    r"choose (?:the )?(?:best|correct) answer|"
    r"以下の.*選択肢|最後の行|回答形式)"
)


@dataclass(frozen=True)
class MCQTask:
    raw: str
    instruction: str
    question: str
    choices: Mapping[str, str]
    domain: str
    answer_contract: bool


@dataclass(frozen=True)
class MCQDecision:
    letter: str
    source: str
    confidence: float
    rationale: str = ""


class StructuredMCQParser:
    """Recognize explicit A-D benchmark/question contracts without hijacking normal chat."""

    def parse(self, text: str) -> MCQTask | None:
        raw = str(text or "").translate(_FULLWIDTH)
        marks = list(_CHOICE_MARKER.finditer(raw))
        if len(marks) != 4:
            return None
        labels = [m.group(1).translate(_FULLWIDTH).upper() for m in marks]
        if labels != ["A", "B", "C", "D"]:
            return None
        if not _CONTRACT_RE.search(raw):
            return None

        choices: dict[str, str] = {}
        for i, mark in enumerate(marks):
            start = mark.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
            value = raw[start:end].strip()
            if not value:
                return None
            choices[labels[i]] = value

        prefix = raw[: marks[0].start()].strip()
        instruction, question = self._split_instruction(prefix)
        if not question:
            return None
        return MCQTask(
            raw=raw,
            instruction=instruction,
            question=question,
            choices=choices,
            domain=self.infer_domain(question, choices.values()),
            answer_contract=True,
        )

    @staticmethod
    def _split_instruction(prefix: str) -> tuple[str, str]:
        blocks = [x.strip() for x in re.split(r"\n\s*\n+", prefix) if x.strip()]
        if len(blocks) >= 2:
            instruction_blocks = []
            question_blocks = []
            seen_question = False
            for block in blocks:
                looks_instruction = bool(_CONTRACT_RE.search(block)) or all(
                    _GENERIC_INSTRUCTION.search(line.strip()) for line in block.splitlines() if line.strip()
                )
                if not seen_question and looks_instruction:
                    instruction_blocks.append(block)
                else:
                    seen_question = True
                    question_blocks.append(block)
            if question_blocks:
                return "\n\n".join(instruction_blocks), "\n\n".join(question_blocks)

        instruction_lines = []
        question_lines = []
        for line in prefix.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _GENERIC_INSTRUCTION.search(stripped) or _CONTRACT_RE.search(stripped):
                instruction_lines.append(stripped)
            else:
                question_lines.append(stripped)
        return "\n".join(instruction_lines), "\n".join(question_lines).strip()

    @staticmethod
    def infer_domain(question: str, choices: Sequence[str]) -> str:
        text = (question + " " + " ".join(choices)).lower()
        domains = {
            "physics": [
                "quantum", "photon", "electron", "hamiltonian", "relativity", "field",
                "momentum", "energy", "spin", "wavefunction", "particle", "boson", "fermion",
            ],
            "biology": [
                "cell", "protein", "gene", "dna", "rna", "enzyme", "organism", "evolution",
                "chromosome", "membrane", "neuron", "species", "molecular biology",
            ],
            "chemistry": [
                "reaction", "molar", "acid", "base", "catalyst", "orbital", "bond",
                "oxidation", "reduction", "solvent", "chemical", "stereochemistry",
            ],
            "mathematics": [
                "theorem", "integral", "derivative", "matrix", "probability", "integer",
                "polynomial", "geometry", "algebra", "topology", "equation",
            ],
            "computer_science": [
                "algorithm", "runtime", "compiler", "program", "graph", "database",
                "complexity", "memory allocation", "network protocol",
            ],
        }
        scored = []
        for name, words in domains.items():
            score = sum(1 for word in words if word in text)
            if score:
                scored.append((score, name))
        if not scored:
            return "general"
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][1]


class StructuredMCQReasoner:
    """Bounded MCQ lane with explicit unresolved fallback labeling."""

    def __init__(self, distilled: Any = None, teacher: Any = None):
        self.distilled = distilled
        self.teacher = teacher

    @staticmethod
    def _answer_from_text(text: str, choices: Mapping[str, str]) -> str | None:
        m = _ANSWER_RE.search(str(text or ""))
        if m and m.group(1).upper() in choices:
            return m.group(1).upper()

        normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
        hits = []
        for letter, value in choices.items():
            v = re.sub(r"\s+", " ", value).strip().lower()
            if len(v) >= 3 and v in normalized:
                hits.append(letter)
        return hits[0] if len(hits) == 1 else None

    @staticmethod
    def _safe_simple_arithmetic(task: MCQTask) -> MCQDecision | None:
        exprs = re.findall(
            r"(?<![A-Za-z0-9_.])(-?\d+(?:\.\d+)?\s*[+\-*/×÷]\s*-?\d+(?:\.\d+)?)(?![A-Za-z0-9_.])",
            task.question,
        )
        if len(exprs) != 1:
            return None
        expr = exprs[0].replace("×", "*").replace("÷", "/")
        try:
            tree = ast.parse(expr, mode="eval")
            node = tree.body
            if not isinstance(node, ast.BinOp):
                return None
            if not isinstance(node.left, ast.Constant) or not isinstance(node.right, ast.Constant):
                return None
            if not isinstance(node.left.value, (int, float)) or not isinstance(node.right.value, (int, float)):
                return None
            ops = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: a / b,
            }
            fn = ops.get(type(node.op))
            if fn is None:
                return None
            value = float(fn(float(node.left.value), float(node.right.value)))
            if not math.isfinite(value):
                return None
        except Exception:
            return None

        matches = []
        for letter, option in task.choices.items():
            cleaned = option.strip().replace(",", "")
            m = re.fullmatch(r"\$?\s*(-?\d+(?:\.\d+)?)\s*\$?", cleaned)
            if m and math.isclose(float(m.group(1)), value, rel_tol=1e-12, abs_tol=1e-12):
                matches.append(letter)
        if len(matches) == 1:
            return MCQDecision(matches[0], "verified_arithmetic", 0.99, f"{expr} = {value:g}")
        return None

    @staticmethod
    def _canonical_prompt(task: MCQTask) -> str:
        rows = [
            "Answer this multiple-choice question.",
            "Return a final line exactly as: Answer: $LETTER",
            "",
            task.question,
            "",
        ]
        rows.extend(f"{letter}) {task.choices[letter]}" for letter in "ABCD")
        return "\n".join(rows)

    @staticmethod
    def _content_fallback(task: MCQTask) -> MCQDecision:
        ranked = []
        q = re.sub(r"\s+", " ", task.question).strip().lower()
        for letter, value in task.choices.items():
            v = re.sub(r"\s+", " ", value).strip().lower()
            digest = hashlib.sha256((q + "\0" + v).encode("utf-8")).digest()
            ranked.append((digest, letter))
        ranked.sort(key=lambda x: x[0])
        return MCQDecision(
            ranked[0][1],
            "unresolved_content_tiebreak",
            0.25,
            "native knowledge/reasoning did not resolve the question",
        )

    def decide(
        self,
        task: MCQTask,
        history: list[Mapping[str, Any]] | None = None,
        *,
        teacher_allowed: bool = False,
    ) -> MCQDecision:
        arithmetic = self._safe_simple_arithmetic(task)
        if arithmetic is not None:
            return arithmetic

        history = list(history or [])
        if self.distilled is not None:
            local = self.distilled.run(task.question, history)
            if local.get("ok") and not local.get("needs_teacher"):
                letter = self._answer_from_text(str(local.get("reply", "")), task.choices)
                if letter:
                    return MCQDecision(letter, "local_distilled_match", 0.55)

        if teacher_allowed and self.teacher is not None:
            try:
                if self.teacher.available():
                    out = self.teacher.run(self._canonical_prompt(task), history)
                    if out.get("ok"):
                        letter = self._answer_from_text(str(out.get("reply", "")), task.choices)
                        if letter:
                            return MCQDecision(letter, "optional_teacher", 0.78)
            except Exception:
                pass

        return self._content_fallback(task)

    def run(
        self,
        task: MCQTask,
        history: list[Mapping[str, Any]] | None = None,
        *,
        teacher_allowed: bool = False,
    ) -> dict[str, Any]:
        decision = self.decide(task, history, teacher_allowed=teacher_allowed)
        lines = []
        if decision.source == "verified_arithmetic" and decision.rationale:
            lines.append(decision.rationale)
        lines.append("Answer: $" + decision.letter)
        return {
            "ok": True,
            "reply": "\n".join(lines),
            "confidence": decision.confidence,
            "decision_source": decision.source,
            "domain": task.domain,
            "forced_choice": decision.source == "unresolved_content_tiebreak",
            "needs_teacher": decision.source == "unresolved_content_tiebreak",
        }


class StructuredMCQVerifier:
    def verify(self, task: MCQTask, result: Mapping[str, Any]) -> tuple[str, str]:
        reply = str(result.get("reply", "")).strip()
        lines = [x.strip() for x in reply.splitlines() if x.strip()]
        if not lines:
            return "NG", "structured MCQ returned an empty reply"
        m = _ANSWER_RE.fullmatch(lines[-1])
        if not m:
            return "NG", "final answer contract was not satisfied"
        letter = m.group(1).upper()
        if letter not in task.choices:
            return "NG", "answer letter is outside the available choices"
        source = str(result.get("decision_source", ""))
        if source == "verified_arithmetic":
            return "OK", "answer contract and deterministic arithmetic verification passed"
        if source == "unresolved_content_tiebreak":
            return "PARTIAL", "answer contract passed; semantic answer remains unresolved"
        return "PARTIAL", f"answer contract passed via {source or 'unverified reasoner'}; no independent answer-key verification"
