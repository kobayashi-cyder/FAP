from __future__ import annotations

import ast
import json
import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Mapping


_TRIGGER = re.compile(
    r"(導出|証明|示して|導いて|derive|derivation|prove|proof|show\s+that)",
    re.I,
)
_JA = re.compile(r"[一-龥ぁ-んァ-ンー]{2,}")
_EN = re.compile(r"[A-Za-z0-9_+\-]{2,}")
_STOP = (
    "について", "に関して", "してください", "して下さい", "ください", "とは",
    "導出", "証明", "示して", "導いて", "derive", "derivation", "prove", "proof",
)

Monomial = tuple[tuple[str, int], ...]
Polynomial = dict[Monomial, Fraction]


@dataclass(frozen=True)
class DerivationPremise:
    equation: str
    label: str = ""
    reason: str = ""


@dataclass(frozen=True)
class DerivationRecord:
    record_id: str
    title: str
    aliases: tuple[str, ...]
    method: str
    construction: str
    variables: tuple[tuple[str, str], ...]
    premises: tuple[DerivationPremise, ...]
    goal: str
    source: str


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower().strip()


def _compact_norm(text: str) -> str:
    return re.sub(r"[\s\-‐‑–—_・･、。，．,:：;；!?！？'\"\x60]+", "", _norm(text))


def _terms(text: str) -> set[str]:
    t = _norm(text)
    for stop in _STOP:
        t = t.replace(stop, " ")
    out = {x.lower() for x in _EN.findall(t)}
    for run in _JA.findall(t):
        if len(run) <= 2:
            out.add(run)
        else:
            for n in (2, 3):
                out.update(run[i : i + n] for i in range(len(run) - n + 1))
    return {x for x in out if len(x) >= 2}


def _clean(poly: Polynomial) -> Polynomial:
    return {m: c for m, c in poly.items() if c}


def _constant(value: Fraction | int) -> Polynomial:
    c = Fraction(value)
    return {} if not c else {(): c}


def _variable(name: str) -> Polynomial:
    return {((name, 1),): Fraction(1)}


def _add(a: Polynomial, b: Polynomial) -> Polynomial:
    out = dict(a)
    for mono, coeff in b.items():
        out[mono] = out.get(mono, Fraction(0)) + coeff
    return _clean(out)


def _scale(a: Polynomial, k: Fraction) -> Polynomial:
    return _clean({m: c * k for m, c in a.items()})


def _mul_monomial(a: Monomial, b: Monomial) -> Monomial:
    exps: dict[str, int] = {}
    for name, power in a + b:
        exps[name] = exps.get(name, 0) + int(power)
    return tuple(sorted((name, power) for name, power in exps.items() if power))


def _mul(a: Polynomial, b: Polynomial) -> Polynomial:
    out: Polynomial = {}
    for ma, ca in a.items():
        for mb, cb in b.items():
            mono = _mul_monomial(ma, mb)
            out[mono] = out.get(mono, Fraction(0)) + ca * cb
            if len(out) > 1024:
                raise ValueError("symbolic expression expanded beyond the safety limit")
    return _clean(out)


def _pow(a: Polynomial, exponent: int) -> Polynomial:
    if exponent < 0 or exponent > 12:
        raise ValueError("only non-negative integer powers up to 12 are supported")
    result = _constant(1)
    base = dict(a)
    n = exponent
    while n:
        if n & 1:
            result = _mul(result, base)
        n >>= 1
        if n:
            base = _mul(base, base)
    return result


def _fraction_from_constant(value: object) -> Fraction:
    if isinstance(value, bool):
        raise ValueError("boolean constants are not allowed")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    raise ValueError("unsupported constant")


def _parse_node(node: ast.AST) -> Polynomial:
    if isinstance(node, ast.Constant):
        return _constant(_fraction_from_constant(node.value))
    if isinstance(node, ast.Name):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", node.id):
            raise ValueError("invalid symbol")
        return _variable(node.id)
    if isinstance(node, ast.UnaryOp):
        value = _parse_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return _scale(value, Fraction(-1))
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left = _parse_node(node.left)
        right = _parse_node(node.right)
        if isinstance(node.op, ast.Add):
            return _add(left, right)
        if isinstance(node.op, ast.Sub):
            return _add(left, _scale(right, Fraction(-1)))
        if isinstance(node.op, ast.Mult):
            return _mul(left, right)
        if isinstance(node.op, ast.Div):
            if set(right) != {()}:
                raise ValueError("division is supported only by numeric constants")
            divisor = right[()]
            if not divisor:
                raise ValueError("division by zero")
            return _scale(left, Fraction(1, 1) / divisor)
        if isinstance(node.op, ast.Pow):
            if set(right) != {()} or right[()].denominator != 1:
                raise ValueError("power must be an integer constant")
            return _pow(left, int(right[()]))
    raise ValueError(f"unsupported syntax: {type(node).__name__}")


def parse_expression(expr: str) -> Polynomial:
    value = str(expr or "").strip().replace("^", "**")
    if not value:
        raise ValueError("empty expression")
    tree = ast.parse(value, mode="eval")
    return _parse_node(tree.body)


def parse_equation(equation: str) -> tuple[Polynomial, Polynomial, Polynomial]:
    text = str(equation or "")
    if text.count("=") != 1:
        raise ValueError("equation must contain exactly one '='")
    lhs_text, rhs_text = text.split("=", 1)
    lhs = parse_expression(lhs_text)
    rhs = parse_expression(rhs_text)
    return lhs, rhs, _add(lhs, _scale(rhs, Fraction(-1)))


def _degree(mono: Monomial) -> int:
    return sum(power for _, power in mono)


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _format_monomial(mono: Monomial) -> str:
    parts: list[str] = []
    for name, power in mono:
        parts.append(name if power == 1 else f"{name}^{power}")
    return "·".join(parts) if parts else "1"


def format_polynomial(poly: Polynomial) -> str:
    rows = sorted(poly.items(), key=lambda item: (-_degree(item[0]), len(item[0]), item[0]))
    if not rows:
        return "0"
    out: list[str] = []
    for mono, coeff in rows:
        sign = "-" if coeff < 0 else "+"
        magnitude = abs(coeff)
        if mono:
            if magnitude == 1:
                body = _format_monomial(mono)
            else:
                body = f"{_format_fraction(magnitude)}·{_format_monomial(mono)}"
        else:
            body = _format_fraction(magnitude)
        if not out:
            out.append(("-" if sign == "-" else "") + body)
        else:
            out.append(f" {sign} {body}")
    return "".join(out)


def _all_monomials(polys: Iterable[Polynomial]) -> list[Monomial]:
    mons: set[Monomial] = set()
    for poly in polys:
        mons.update(poly)
    return sorted(mons, key=lambda m: (-_degree(m), m))


def solve_linear_span(premises: list[Polynomial], target: Polynomial) -> list[Fraction] | None:
    """Return coefficients c with sum(c_i * premise_i) == target.

    Equality relations are represented as polynomials equal to zero. Showing
    that the target relation is in the linear span of verified premise
    relations is a generic algebraic entailment check; it contains no
    theorem-specific rewrite branch.
    """
    if not premises:
        return [] if not target else None
    if not target:
        return [Fraction(0) for _ in premises]

    mons = _all_monomials([*premises, target])
    n = len(premises)
    matrix: list[list[Fraction]] = []
    for mono in mons:
        row = [poly.get(mono, Fraction(0)) for poly in premises]
        row.append(target.get(mono, Fraction(0)))
        matrix.append(row)

    pivot_rows: dict[int, int] = {}
    row_index = 0
    for col in range(n):
        pivot = next((r for r in range(row_index, len(matrix)) if matrix[r][col]), None)
        if pivot is None:
            continue
        matrix[row_index], matrix[pivot] = matrix[pivot], matrix[row_index]
        scale = matrix[row_index][col]
        matrix[row_index] = [x / scale for x in matrix[row_index]]
        for r in range(len(matrix)):
            if r == row_index:
                continue
            factor = matrix[r][col]
            if factor:
                matrix[r] = [x - factor * y for x, y in zip(matrix[r], matrix[row_index])]
        pivot_rows[col] = row_index
        row_index += 1
        if row_index >= len(matrix):
            break

    for row in matrix:
        if all(not row[c] for c in range(n)) and row[n]:
            return None

    solution = [Fraction(0) for _ in range(n)]
    for col, r in sorted(pivot_rows.items(), reverse=True):
        rhs = matrix[r][n]
        rhs -= sum(matrix[r][j] * solution[j] for j in range(col + 1, n))
        solution[col] = rhs

    reconstructed: Polynomial = {}
    for coeff, poly in zip(solution, premises):
        reconstructed = _add(reconstructed, _scale(poly, coeff))
    return solution if _clean(reconstructed) == _clean(target) else None


def _eval_poly(poly: Polynomial, values: Mapping[str, Fraction]) -> Fraction:
    total = Fraction(0)
    for mono, coeff in poly.items():
        value = coeff
        for name, power in mono:
            value *= values[name] ** power
        total += value
    return total


def _countercheck(premises: list[Polynomial], target: Polynomial, coefficients: list[Fraction]) -> bool:
    symbols = sorted({name for poly in [*premises, target] for mono in poly for name, _ in mono})
    seeds = (2, 3, 5, 7, 11)
    for offset in range(5):
        values = {name: Fraction(seeds[(i + offset) % len(seeds)]) for i, name in enumerate(symbols)}
        left = _eval_poly(target, values)
        right = sum((c * _eval_poly(p, values) for c, p in zip(coefficients, premises)), Fraction(0))
        if left != right:
            return False
    return True


class GenericDerivationEngine:
    """Data-driven local derivation with symbolic verification.

    The engine does not branch on theorem names. Mathematical subject matter
    lives in knowledge/*.jsonl records. Code only performs retrieval, safe
    symbolic normalization, algebraic entailment and an independent numeric
    countercheck.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._records: tuple[DerivationRecord, ...] | None = None

    def _load(self) -> tuple[DerivationRecord, ...]:
        records: list[DerivationRecord] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            return ()
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line_no, line in enumerate(lines, 1):
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict) or row.get("kind") != "algebraic_derivation":
                    continue
                premises_raw = row.get("premises") or []
                premises: list[DerivationPremise] = []
                for item in premises_raw:
                    if isinstance(item, str):
                        premises.append(DerivationPremise(item))
                    elif isinstance(item, dict) and str(item.get("equation", "")).strip():
                        premises.append(DerivationPremise(
                            equation=str(item.get("equation", "")).strip(),
                            label=str(item.get("label", "")).strip(),
                            reason=str(item.get("reason", "")).strip(),
                        ))
                goal = str(row.get("goal", "")).strip()
                if not premises or not goal:
                    continue
                variables = row.get("variables") or {}
                if isinstance(variables, dict):
                    var_rows = tuple((str(k), str(v)) for k, v in variables.items())
                else:
                    var_rows = ()
                records.append(DerivationRecord(
                    record_id=str(row.get("id") or f"{path.stem}:{line_no}"),
                    title=str(row.get("title") or row.get("id") or "derivation"),
                    aliases=tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                    method=str(row.get("method") or "代数的整理"),
                    construction=str(row.get("construction") or row.get("text") or "").strip(),
                    variables=var_rows,
                    premises=tuple(premises),
                    goal=goal,
                    source=str(path.relative_to(self.root)),
                ))
        return tuple(records)

    @property
    def records(self) -> tuple[DerivationRecord, ...]:
        if self._records is None:
            self._records = self._load()
        return self._records

    def refresh(self) -> None:
        self._records = None

    @staticmethod
    def _history_context(history: list[Mapping], limit: int = 6) -> str:
        rows: list[str] = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:320])
        return " ".join(rows)

    def _score(self, record: DerivationRecord, query: str, context: str) -> float:
        qn = _compact_norm(query)
        qterms = _terms(query)
        cterms = _terms(context)
        names = (record.title, *record.aliases)
        score = 0.0
        for name in names:
            nn = _compact_norm(name)
            if nn and nn in qn:
                score = max(score, 9.0 + min(2.0, len(nn) / 8.0))
        record_terms = _terms(" ".join([record.title, *record.aliases, record.construction]))
        if qterms and record_terms:
            score += 4.0 * len(qterms & record_terms) / max(1, len(qterms))
        if cterms and record_terms:
            score += 0.8 * len(cterms & record_terms) / max(1, len(cterms))
        return score

    def _select(self, text: str, history: list[Mapping]) -> tuple[DerivationRecord | None, float]:
        context = self._history_context(history)
        ranked = sorted(
            ((self._score(record, text, context), record) for record in self.records),
            key=lambda item: (-item[0], item[1].record_id),
        )
        if not ranked or ranked[0][0] < 3.0:
            return None, 0.0
        return ranked[0][1], ranked[0][0]

    @staticmethod
    def _render(
        record: DerivationRecord,
        parsed: list[tuple[DerivationPremise, Polynomial, Polynomial, Polynomial]],
        target: Polynomial,
        coefficients: list[Fraction],
    ) -> str:
        lines: list[str] = [f"{record.title}を、{record.method}で導出します。"]
        if record.variables:
            variables = "、".join(f"{name}={meaning}" for name, meaning in record.variables)
            lines.append(f"記号は {variables} とします。")
        if record.construction:
            lines.append(record.construction)

        for idx, (premise, lhs, rhs, diff) in enumerate(parsed, 1):
            label = premise.label or f"前提{idx}"
            lines.append(f"{idx}. {label}: {premise.equation}")
            expanded_lhs = format_polynomial(lhs)
            expanded_rhs = format_polynomial(rhs)
            if expanded_lhs != premise.equation.split("=", 1)[0].strip() or expanded_rhs != premise.equation.split("=", 1)[1].strip():
                lines.append(f"   展開すると {expanded_lhs} = {expanded_rhs}。")
            if premise.reason:
                lines.append(f"   根拠: {premise.reason}")
            lines.append(f"   標準形は {format_polynomial(diff)} = 0。")

        active = [(i + 1, c) for i, c in enumerate(coefficients) if c]
        if len(active) == 1 and active[0][1] == 1:
            lines.append("この標準形を整理すると目標式と同値になります。")
        elif active:
            combo = " + ".join(f"({_format_fraction(c)})×式{i}" for i, c in active)
            lines.append(f"これらの等式を {combo} として組み合わせ、同類項を整理します。")
        else:
            lines.append("目標式は恒等的に成り立つ形へ正規化されます。")
        lines.append(f"したがって {record.goal}。")
        lines.append("最後に、同じ関係を別の数値代入でも照合し、記号整理との不一致がないことを確認しました。")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        query = str(text or "").strip()
        if not query or not _TRIGGER.search(query):
            return None
        record, score = self._select(query, history)
        if record is None:
            return None

        parsed: list[tuple[DerivationPremise, Polynomial, Polynomial, Polynomial]] = []
        try:
            for premise in record.premises:
                lhs, rhs, diff = parse_equation(premise.equation)
                parsed.append((premise, lhs, rhs, diff))
            _, _, target = parse_equation(record.goal)
        except (SyntaxError, ValueError, ZeroDivisionError) as exc:
            return {
                "ok": False,
                "reply": f"導出データは見つかりましたが、記号式を安全に解釈できませんでした: {exc}",
                "confidence": 0.35,
                "needs_teacher": False,
                "derivation_reasoning": True,
                "derivation_verified": False,
                "derivation_id": record.record_id,
                "route_tags": ["derivation-retrieve", "symbolic-normalize", "verify-failed"],
            }

        premise_polys = [row[3] for row in parsed]
        coefficients = solve_linear_span(premise_polys, target)
        verified = coefficients is not None and _countercheck(premise_polys, target, coefficients)
        if not verified:
            return {
                "ok": False,
                "reply": "関連する導出データは取得できましたが、目標式が前提式から記号的に導けることを検証できませんでした。",
                "confidence": 0.42,
                "needs_teacher": False,
                "derivation_reasoning": True,
                "derivation_verified": False,
                "derivation_id": record.record_id,
                "evidence_ids": [record.record_id],
                "route_tags": ["derivation-retrieve", "symbolic-normalize", "algebraic-entailment", "verify-failed"],
            }

        return {
            "ok": True,
            "reply": self._render(record, parsed, target, coefficients),
            "confidence": min(0.99, 0.93 + min(0.05, score / 100.0)),
            "needs_teacher": False,
            "local": True,
            "grounded": True,
            "derivation_reasoning": True,
            "derivation_verified": True,
            "derivation_id": record.record_id,
            "derivation_source": record.source,
            "derivation_goal": record.goal,
            "derivation_coefficients": [_format_fraction(x) for x in coefficients],
            "evidence_ids": [record.record_id],
            "route_tags": [
                "derivation-retrieve",
                "symbolic-normalize",
                "algebraic-entailment",
                "independent-countercheck",
            ],
        }
