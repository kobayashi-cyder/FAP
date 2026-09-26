from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import re
from typing import Any, Mapping


_ARITH_CHUNK = re.compile(r"[0-9eE.+\-*/%()\s]{3,}")
_MATH_CUE = re.compile(r"(計算|式|いくら|求め|calculate|compute|evaluate|=)", re.I)
_CAUSAL = re.compile(r"(なぜ|どうして|原因|因果|影響|理由|why\b|cause|causal|effect)", re.I)
_CODE = re.compile(r"(python|c\+\+|\bc\b|java|kotlin|javascript|typescript|html|css|コード|実装|関数|プログラム|script)", re.I)
_CREATE = re.compile(r"(作って|作成|生成|書いて|実装|構築|build|create|make|implement|write)", re.I)
_CONSTRAINT = re.compile(
    r"(?:必ず|絶対|のみ|だけ|以内|以下|以上|未満|超え|禁止|しないで|使わない|必要|必須|"
    r"must\b|only\b|without\b|do not\b|don't\b|never\b|at most\b|at least\b)",
    re.I,
)
_TOKEN = re.compile(r"[一-龥ぁ-んァ-ンー]{2,}|[A-Za-z0-9_+.-]{2,}")
_SPLIT = re.compile(r"[\n。！？!?;；]+")


def _clip(value: object, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(x):
        return default
    return max(0.0, min(1.0, x))


def _features(text: str) -> set[str]:
    value = str(text or "").casefold()
    out: set[str] = set()
    for token in _TOKEN.findall(value):
        if re.search(r"[一-龥ぁ-んァ-ンー]", token):
            if len(token) <= 2:
                out.add(token)
            else:
                out.update(token[i : i + 2] for i in range(len(token) - 1))
        else:
            out.add(token)
    return out


def lexical_overlap(a: str, b: str) -> float:
    x, y = _features(a), _features(b)
    if not x or not y:
        return 0.0
    return len(x & y) / max(1, len(x | y))


class SafeArithmeticSpecialist:
    """Dependency-free arithmetic specialist with a strict AST allowlist."""

    ALLOWED = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a**b,
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    @classmethod
    def _eval(cls, node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return cls._eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.ALLOWED:
            return cls.ALLOWED[type(node.op)](cls._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in cls.ALLOWED:
            a, b = cls._eval(node.left), cls._eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(float(b)) > 12:
                raise ValueError("exponent too large")
            value = cls.ALLOWED[type(node.op)](a, b)
            if not math.isfinite(float(value)) or abs(float(value)) > 1e18:
                raise ValueError("result out of range")
            return value
        raise ValueError("unsupported expression")

    def run(self, text: str) -> dict[str, Any] | None:
        raw_text = str(text or "")
        normalized = raw_text.replace("×", "*").replace("÷", "/").replace("^", "**")
        chunks = sorted(
            (x.strip() for x in _ARITH_CHUNK.findall(normalized)),
            key=len,
            reverse=True,
        )
        only_expression = bool(normalized.strip()) and all(
            ch in "0123456789eE.+-*/%() \t\r\n" for ch in normalized.strip()
        )
        if not (_MATH_CUE.search(raw_text) or only_expression):
            return None

        for expr in chunks:
            if not re.search(r"\d", expr):
                continue
            if not re.search(r"(?:\*\*|[+\-*/%])", expr):
                continue
            try:
                value = self._eval(ast.parse(expr, mode="eval"))
            except Exception:
                continue
            return {
                "ok": True,
                "reply": f"{expr} = {value}",
                "confidence": 0.995,
                "verified": True,
                "grounded": True,
                "local": True,
                "arithmetic_verified": True,
                "decision_source": "verified_arithmetic",
            }
        return None


class CausalFrameSpecialist:
    """Generate a falsifiable causal frame without inventing domain facts."""

    def run(self, text: str) -> dict[str, Any] | None:
        value = str(text or "").strip()
        if not value or not _CAUSAL.search(value):
            return None
        return {
            "ok": True,
            "reply": (
                "因果としては、①観測された現象、②原因候補、③両者を結ぶ機構、"
                "④交絡要因、⑤反証できる観測を分けると検証しやすいです。"
                "この枠組みだけでは原因を確定せず、対象固有の証拠がある候補を優先します。"
            ),
            "confidence": 0.58,
            "verified": False,
            "grounded": False,
            "needs_teacher": True,
            "local": True,
            "causal_frame": True,
        }


class CodePlanningSpecialist:
    """Read-only coding planner. It never writes files or executes generated code."""

    LANGS = (
        ("C++", re.compile(r"c\+\+", re.I)),
        ("C", re.compile(r"(?<!\w)c(?!\w)", re.I)),
        ("Python", re.compile(r"python|\.py\b", re.I)),
        ("Kotlin", re.compile(r"kotlin", re.I)),
        ("Java", re.compile(r"java", re.I)),
        ("TypeScript", re.compile(r"typescript|\bts\b", re.I)),
        ("JavaScript", re.compile(r"javascript|\bjs\b", re.I)),
        ("HTML", re.compile(r"html|web|ブラウザ", re.I)),
    )

    def run(self, text: str) -> dict[str, Any] | None:
        value = str(text or "").strip()
        if not value or not (_CODE.search(value) and _CREATE.search(value)):
            return None
        language = next((name for name, rx in self.LANGS if rx.search(value)), "unspecified")
        requirements = RequirementCoverageAuditor.extract_constraints(value)
        req = " / ".join(requirements[:4]) if requirements else "明示制約なし"
        return {
            "ok": True,
            "reply": (
                f"実装計画: language={language}。"
                "要求を入力/出力・状態・失敗条件・検証条件へ分解し、最小実装→静的検証→"
                f"回帰テストの順で組みます。制約: {req}"
            ),
            "confidence": 0.68,
            "verified": False,
            "grounded": True,
            "local": True,
            "code_plan": True,
            "partial": True,
        }


class RequirementCoverageAuditor:
    @staticmethod
    def extract_constraints(text: str) -> list[str]:
        rows: list[str] = []
        for chunk in _SPLIT.split(str(text or "")):
            value = chunk.strip()
            if value and _CONSTRAINT.search(value):
                rows.append(value[:240])
        return rows[:12]

    def score(self, request: str, reply: str) -> float:
        constraints = self.extract_constraints(request)
        if not constraints:
            return 1.0
        scores = []
        for row in constraints:
            scores.append(max(lexical_overlap(row, reply), 0.0))
        return _clip(sum(scores) / max(1, len(scores)) * 3.0)


class SegmentCoverageAuditor:
    """Estimate how much of a multi-part request is represented in a reply."""

    def score(self, request: str, reply: str) -> float:
        segments = [x.strip() for x in _SPLIT.split(str(request or "")) if len(x.strip()) >= 3]
        if not segments:
            return 1.0 if str(reply or "").strip() else 0.0
        scores = [lexical_overlap(x, reply) for x in segments[:16]]
        # Partial coverage is intentional; reward useful breadth without requiring 100%.
        covered = sum(1 for x in scores if x >= 0.035)
        soft = sum(min(1.0, x / 0.10) for x in scores) / len(scores)
        return _clip(0.60 * (covered / len(scores)) + 0.40 * soft)


@dataclass(frozen=True)
class AuditBundle:
    requirement_coverage: float
    segment_coverage: float

    @property
    def combined(self) -> float:
        return _clip(0.45 * self.requirement_coverage + 0.55 * self.segment_coverage)


class ResponseAuditor:
    def __init__(self) -> None:
        self.requirements = RequirementCoverageAuditor()
        self.segments = SegmentCoverageAuditor()

    def audit(self, request: str, reply: str) -> AuditBundle:
        return AuditBundle(
            requirement_coverage=self.requirements.score(request, reply),
            segment_coverage=self.segments.score(request, reply),
        )
