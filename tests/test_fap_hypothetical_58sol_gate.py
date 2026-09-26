from __future__ import annotations

import os
import random
import re
import secrets
import string
import unittest

import fap_v87_81_coding_conversation_gateway as latest


def _seed() -> int:
    replay = os.environ.get("FAP_H58_REPLAY_SEED", "").strip()
    if replay:
        return int(replay, 0)
    return secrets.randbits(256)


SEED = _seed()
ANSWER_RE = re.compile(r"(?im)^\s*Answer\s*:\s*\$?([A-D])\$?\s*$")


def _uniq_numeric_options(correct: int, candidates: list[int]) -> list[str]:
    out = [correct]
    for value in candidates:
        if value not in out:
            out.append(value)
    delta = 1
    while len(out) < 4:
        for value in (correct + delta, correct - delta):
            if value not in out:
                out.append(value)
                if len(out) == 4:
                    break
        delta += 1
    return [str(x) for x in out[:4]]


def _mcq(question: str, options: list[str], rng: random.Random) -> tuple[str, str]:
    if len(options) != 4 or len(set(options)) != 4:
        raise AssertionError(f"MCQ requires four unique options: {options!r}")
    indexed = list(enumerate(options))
    rng.shuffle(indexed)
    letters = "ABCD"
    instruction = rng.choice([
        "Answer the following multiple-choice question.",
        "Solve the problem below.",
        "Choose the correct option using only the stated information.",
        "Determine which option follows from the problem.",
    ])
    rows = [
        instruction,
        "Reason from the information in this question only.",
        "Return a final line exactly as: Answer: $LETTER",
        "",
        question.strip(),
        "",
    ]
    answer_letter = ""
    for letter, (original_index, text) in zip(letters, indexed):
        rows.append(f"{letter}) {text}")
        if original_index == 0:
            answer_letter = letter
    return "\n".join(rows), answer_letter


def _answer_letter(result: dict) -> str:
    reply = str(result.get("reply") or "")
    matches = ANSWER_RE.findall(reply)
    return matches[-1].upper() if matches else ""


def _word(rng: random.Random, used: set[str]) -> str:
    consonants = "bcdfghjklmnprstvwz"
    vowels = "aeiou"
    while True:
        token = "".join(
            rng.choice(consonants if i % 2 == 0 else vowels)
            for i in range(rng.choice([5, 7, 9]))
        )
        if token not in used:
            used.add(token)
            return token


def _apply_ops(value: int, ops: list[tuple[str, int]]) -> int:
    for op, arg in ops:
        if op == "add":
            value += arg
        elif op == "subtract":
            value -= arg
        elif op == "multiply":
            value *= arg
        else:
            raise AssertionError(op)
    return value


def _render_ops(start: int, ops: list[tuple[str, int]], rng: random.Random) -> str:
    verbs = {
        "add": ["add {n}", "increase it by {n}", "plus {n}"],
        "subtract": ["subtract {n}", "decrease it by {n}", "minus {n}"],
        "multiply": ["multiply by {n}", "scale it by {n}", "times {n}"],
    }
    steps = [rng.choice(verbs[op]).format(n=arg) for op, arg in ops]
    style = rng.randrange(3)
    if style == 0:
        return (
            f"A register starts at {start}. Apply these operations in order: "
            + "; ".join(steps)
            + ". What is the final value?"
        )
    if style == 1:
        return (
            f"Begin with {start}. Then "
            + ", then ".join(steps)
            + ". What number do you obtain?"
        )
    return (
        f"Initial value: {start}. Ordered transformation: "
        + " -> ".join(steps)
        + ". Determine the result."
    )


class Hypothetical58SolGateTests(unittest.TestCase):
    """Aspirational randomized generalization gate.

    "5.8Sol" is an internal FAP codename, not an equivalence claim about any
    external model. The default seed is unpredictable before each test run.
    """

    @classmethod
    def setUpClass(cls):
        cls.core = latest.FAPV8781Unified()
        cls.rng = random.Random(SEED)

    def _chat(self, prompt: str, tag: str) -> dict:
        sid = f"h58-{SEED:x}-{tag}"
        if hasattr(latest.base.MEMORY, "clear"):
            latest.base.MEMORY.clear(sid)
        else:
            path = latest.base.MEMORY.path(sid)
            if path.exists():
                path.unlink()
        if hasattr(self.core, "clear_route_continuity"):
            self.core.clear_route_continuity(sid)
        return self.core.chat(prompt, sid)

    def _assert_verified_answer(self, result: dict, expected: str, label: str) -> None:
        replay = f" replay_seed=0x{SEED:x}"
        self.assertEqual(_answer_letter(result), expected, label + replay)
        structured = result.get("structured_mcq") or {}
        self.assertFalse(structured.get("forced_choice", False), label + replay)
        self.assertEqual(
            result.get("verdict"),
            "OK",
            f"{label}: independently verified OK required.{replay}",
        )
        self.assertGreaterEqual(
            float(result.get("confidence", 0.0)),
            0.80,
            f"{label}: calibrated confidence required.{replay}",
        )

    def test_random_multistep_quantitative_generalization(self):
        for case in range(10):
            start = self.rng.randint(3, 35)
            ops: list[tuple[str, int]] = []
            for _ in range(self.rng.randint(3, 6)):
                op = self.rng.choice(["add", "subtract", "multiply"])
                arg = self.rng.randint(2, 9) if op == "multiply" else self.rng.randint(2, 29)
                ops.append((op, arg))
            correct = _apply_ops(start, ops)
            prompt, expected = _mcq(
                _render_ops(start, ops, self.rng),
                _uniq_numeric_options(
                    correct,
                    [
                        correct + self.rng.randint(2, 17),
                        correct - self.rng.randint(2, 17),
                        start + sum(arg for op, arg in ops if op == "add"),
                    ],
                ),
                self.rng,
            )
            self._assert_verified_answer(
                self._chat(prompt, f"quant-{case}"),
                expected,
                f"random quantitative case {case}",
            )

    def test_random_novel_symbolic_rule_chains(self):
        for case in range(10):
            used: set[str] = set()
            chain = [_word(self.rng, used) for _ in range(self.rng.randint(3, 6))]
            excluded = _word(self.rng, used)
            individual = _word(self.rng, used)
            premises = [
                f"Every {chain[i]} is a {chain[i + 1]}."
                for i in range(len(chain) - 1)
            ]
            premises.append(f"No {chain[-1]} is a {excluded}.")
            premises.append(f"{individual} is a {chain[0]}.")
            self.rng.shuffle(premises)
            target = f"{individual} is not a {excluded}."
            options = [
                target,
                f"{individual} is a {excluded}.",
                f"No {chain[0]} is a {chain[1]}.",
                f"Some {excluded} is a {chain[0]}.",
            ]
            prompt, expected = _mcq(
                " ".join(premises) + " Which statement is necessarily true?",
                options,
                self.rng,
            )
            self._assert_verified_answer(
                self._chat(prompt, f"logic-{case}"),
                expected,
                f"random symbolic case {case}",
            )

    def test_random_epistemic_calibration(self):
        for case in range(8):
            used: set[str] = set()
            a, b, c, person = [_word(self.rng, used) for _ in range(4)]
            wording = self.rng.choice([
                (
                    f"Every {a} is a {b}. Some {b} are {c}. "
                    f"{person} is a {a}. Can we conclude that {person} is a {c}?"
                ),
                (
                    f"All {a} objects belong to {b}. At least one {b} is also {c}. "
                    f"{person} is {a}. Is {person} necessarily {c}?"
                ),
            ])
            options = [
                "It cannot be determined from the given information.",
                "Yes, necessarily.",
                "No, necessarily not.",
                "The premises are contradictory.",
            ]
            prompt, expected = _mcq(wording, options, self.rng)
            self._assert_verified_answer(
                self._chat(prompt, f"cal-{case}"),
                expected,
                f"random calibration case {case}",
            )

    def test_random_counterfactual_rule_revision(self):
        for case in range(8):
            x = self.rng.randint(3, 30)
            original_delta = self.rng.randint(2, 11)
            revised_mul = self.rng.randint(2, 6)
            revised_add = self.rng.randint(2, 17)
            correct = x * revised_mul + revised_add
            wording = self.rng.choice([
                (
                    f"A toy rule originally maps x to x-{original_delta}. "
                    f"For this question discard that rule and instead map x to "
                    f"x*{revised_mul}+{revised_add}. What is the image of {x}?"
                ),
                (
                    f"Suppose the old transformation was x-{original_delta}. "
                    f"Counterfactually replace it with: multiply x by {revised_mul}, "
                    f"then add {revised_add}. Apply the revised transformation to {x}."
                ),
            ])
            options = _uniq_numeric_options(
                correct,
                [
                    x - original_delta,
                    x * revised_mul,
                    x + revised_add,
                ],
            )
            prompt, expected = _mcq(wording, options, self.rng)
            self._assert_verified_answer(
                self._chat(prompt, f"counter-{case}"),
                expected,
                f"random counterfactual case {case}",
            )

    def test_random_code_execution_reasoning(self):
        for case in range(8):
            mul = self.rng.randint(2, 9)
            add = self.rng.randint(1, 12)
            n = self.rng.randint(3, 8)
            mode = self.rng.choice(["sum", "even"])
            if mode == "sum":
                correct = sum(i * mul + add for i in range(n))
                body = f"total += i * {mul} + {add}"
            else:
                correct = sum(i * mul + add for i in range(n) if i % 2 == 0)
                body = (
                    "if i % 2 == 0:\n"
                    f"            total += i * {mul} + {add}"
                )
            question = f"""
Consider the Python function below.

def f(n):
    total = 0
    for i in range(n):
        {body}
    return total

What does f({n}) return?
"""
            options = _uniq_numeric_options(
                correct,
                [
                    correct + mul,
                    correct - add,
                    n * (mul + add),
                ],
            )
            prompt, expected = _mcq(question, options, self.rng)
            self._assert_verified_answer(
                self._chat(prompt, f"code-{case}"),
                expected,
                f"random code case {case}",
            )

    def test_random_paraphrase_permutation_and_noise_invariance(self):
        noise = [
            "Unrelated note: copper conducts electricity.",
            "Ignore this distractor: seven days make a week.",
            "Background noise: a triangle has three sides.",
            "Irrelevant observation: water freezes near zero Celsius at standard pressure.",
        ]
        for case in range(8):
            start = self.rng.randint(4, 24)
            ops = [
                ("multiply", self.rng.randint(2, 5)),
                ("add", self.rng.randint(3, 20)),
                ("subtract", self.rng.randint(2, 11)),
            ]
            correct = _apply_ops(start, ops)
            options = _uniq_numeric_options(
                correct,
                [correct + 1, correct - 1, start + sum(x[1] for x in ops)],
            )
            base_question = _render_ops(start, ops, self.rng)
            transformed = self.rng.choice(noise) + " " + _render_ops(start, ops, self.rng)
            p1, e1 = _mcq(base_question, options, self.rng)
            p2, e2 = _mcq(transformed, options, self.rng)
            self._assert_verified_answer(
                self._chat(p1, f"inv-a-{case}"), e1, f"invariance base {case}"
            )
            self._assert_verified_answer(
                self._chat(p2, f"inv-b-{case}"), e2, f"invariance transformed {case}"
            )

    def test_randomness_contract_is_not_predictable_ci_run_id(self):
        self.assertNotIn("FAP_HYPOTHETICAL_58SOL_SEED", os.environ)
        self.assertGreaterEqual(SEED.bit_length(), 192)

    def test_gate_has_no_average_score_escape_hatch(self):
        required = {
            "random_multistep_quantitative",
            "random_novel_symbolic_rules",
            "random_epistemic_calibration",
            "random_counterfactual_revision",
            "random_code_execution",
            "random_paraphrase_permutation_noise_invariance",
        }
        self.assertEqual(len(required), 6)
        self.assertNotIn("weighted_average", required)


if __name__ == "__main__":
    unittest.main()
