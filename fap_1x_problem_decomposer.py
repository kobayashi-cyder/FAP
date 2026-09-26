from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(frozen=True)
class Subproblem:
    subproblem_id: str
    kind: str
    objective: str
    depends_on: tuple[str, ...] = ()
    verification: str = "semantic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProblemDecomposition:
    task_kind: str
    objective: str
    constraints: tuple[str, ...]
    givens: tuple[str, ...]
    unknowns: tuple[str, ...]
    subproblems: tuple[Subproblem, ...]
    risk: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_kind": self.task_kind,
            "objective": self.objective,
            "constraints": list(self.constraints),
            "givens": list(self.givens),
            "unknowns": list(self.unknowns),
            "subproblems": [row.to_dict() for row in self.subproblems],
            "risk": self.risk,
        }


class ProblemDecomposer:
    """Generic, domain-light task decomposition.

    The decomposer extracts explicit goals/constraints and emits a dependency
    graph. It never inserts an answer or benchmark-specific fact.
    """

    _CALC = re.compile(r"(計算|求め|何(?:度|個|円|m|kg|s|v|a|w)?\b|calculate|compute|find\s+(?:the\s+)?(?:value|number|voltage|current))", re.I)
    _DERIVE = re.compile(r"(導出|証明|示して|derive|prove|proof|show\s+that)", re.I)
    _EXPLAIN = re.compile(r"(説明|なぜ|理由|どうして|why|explain|reason)", re.I)
    _COMPARE = re.compile(r"(比較|違い|差|どちら|compare|difference|versus|\bvs\b)", re.I)
    _PLAN = re.compile(r"(計画|手順|設計|方法|どうすれば|plan|design|steps|approach)", re.I)
    _CODE = re.compile(r"(コード|実装|バグ|修正|関数|class|repository|code|implement|bug|function)", re.I)
    _HYP = re.compile(r"(仮説|可能性|反証|検証案|hypothes|possible cause|falsif)", re.I)
    _CONSTRAINT = re.compile(
        r"(?:[^。.!?！？]{0,60}"
        r"(?:以内|以上|以下|未満|必須|禁止|のみ|だけ|せず|してはいけない|"
        r"must|must not|without|at most|at least|only|no more than)"
        r"[^。.!?！？]{0,80})",
        re.I,
    )
    _NUMBER_GIVEN = re.compile(
        r"(?:[A-Za-z_][A-Za-z0-9_ ]{0,24}\s*(?:=|is|:)?\s*)?"
        r"-?\d+(?:\.\d+)?(?:\s*(?:%|[A-Za-zΩ°/²³^_-]+))?"
    )
    _UNKNOWN = re.compile(
        r"(?:何|どの|どれ|求め|計算|未知|unknown|what|which|find|determine)\s*"
        r"([^。.!?！？,，]{0,50})",
        re.I,
    )

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n,，。.!?！？;；:")

    def classify(self, text: str) -> str:
        query = self._clean(text)
        for name, pattern in (
            ("coding", self._CODE),
            ("derivation", self._DERIVE),
            ("calculation", self._CALC),
            ("comparison", self._COMPARE),
            ("hypothesis", self._HYP),
            ("planning", self._PLAN),
            ("explanation", self._EXPLAIN),
        ):
            if pattern.search(query):
                return name
        return "open"

    def decompose(self, text: str) -> ProblemDecomposition:
        query = self._clean(text)
        kind = self.classify(query)
        constraints = tuple(
            dict.fromkeys(
                self._clean(match.group(0))
                for match in self._CONSTRAINT.finditer(query)
                if self._clean(match.group(0))
            )
        )[:12]
        givens = tuple(
            dict.fromkeys(
                self._clean(match.group(0))
                for match in self._NUMBER_GIVEN.finditer(query)
                if self._clean(match.group(0))
            )
        )[:16]
        unknowns = tuple(
            dict.fromkeys(
                self._clean(match.group(1))
                for match in self._UNKNOWN.finditer(query)
                if self._clean(match.group(1))
            )
        )[:8]

        rows: list[Subproblem] = [
            Subproblem(
                "interpret",
                "interpretation",
                "Normalize the request, target and explicit constraints.",
                (),
                "constraint_consistency",
            )
        ]
        if givens:
            rows.append(
                Subproblem(
                    "ground",
                    "grounding",
                    "Bind quantities, entities and units to a consistent internal representation.",
                    ("interpret",),
                    "type_and_unit_check",
                )
            )
            parent = "ground"
        else:
            parent = "interpret"

        if kind in {"calculation", "derivation"}:
            rows.append(
                Subproblem(
                    "derive",
                    "derivation",
                    "Construct a candidate result from the available relations without using the answer choices as evidence.",
                    (parent,),
                    "independent_recompute",
                )
            )
            solve_parent = "derive"
        elif kind == "coding":
            rows.append(
                Subproblem(
                    "inspect",
                    "repository_analysis",
                    "Locate relevant symbols, dependencies, tests and failure evidence.",
                    (parent,),
                    "repository_evidence",
                )
            )
            rows.append(
                Subproblem(
                    "patch",
                    "candidate_generation",
                    "Generate the smallest candidate change that satisfies the requested behavior.",
                    ("inspect",),
                    "compile_or_test",
                )
            )
            solve_parent = "patch"
        elif kind == "hypothesis":
            rows.append(
                Subproblem(
                    "alternatives",
                    "abduction",
                    "Generate competing explanations rather than a single favored story.",
                    (parent,),
                    "falsifiability",
                )
            )
            solve_parent = "alternatives"
        else:
            rows.append(
                Subproblem(
                    "candidates",
                    "candidate_generation",
                    "Generate at least one grounded answer candidate and preserve alternatives when evidence conflicts.",
                    (parent,),
                    "evidence_check",
                )
            )
            solve_parent = "candidates"

        rows.append(
            Subproblem(
                "verify",
                "verification",
                "Check the candidate with a method independent from the generator where possible.",
                (solve_parent,),
                "independent_verifier",
            )
        )
        rows.append(
            Subproblem(
                "counterexample",
                "critique",
                "Search for a counterexample, contradiction, unit mismatch or unsupported assumption.",
                ("verify",),
                "counterexample_search",
            )
        )
        rows.append(
            Subproblem(
                "synthesize",
                "synthesis",
                "Return the strongest supported result or explicitly abstain when verification remains insufficient.",
                ("counterexample",),
                "calibration",
            )
        )

        risk = 0.20
        risk += 0.18 if len(query) > 320 else 0.0
        risk += 0.14 if len(constraints) >= 2 else 0.0
        risk += 0.18 if kind in {"coding", "derivation", "hypothesis"} else 0.0
        risk += 0.12 if re.search(r"(最新|current|today|web|外部|法律|医療|金融)", query, re.I) else 0.0
        risk = min(1.0, risk)

        return ProblemDecomposition(
            task_kind=kind,
            objective=query[:1200],
            constraints=constraints,
            givens=givens,
            unknowns=unknowns,
            subproblems=tuple(rows),
            risk=round(risk, 3),
        )
