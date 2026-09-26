from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping


_EXPR_CHUNK = re.compile(r"[0-9eE.+\-*/%()\s]{3,}")
_MATH_TRIGGER = re.compile(r"(計算|evaluate|calculate|それぞれ|each|複数|multi)", re.I)
_CODE_BLOCK = re.compile(r"`{3}(?:python|py)?\s*\n(.*?)`{3}", re.I | re.S)
_COUNTER_CUE = re.compile(r"(反例|counterexample|always|never|すべて|全て|必ず|絶対|例外)", re.I)
_CAUSAL_ARROW = re.compile(r"([^\n。！？;；]{1,80}?)\s*(?:->|→|⇒|causes?|leads? to|が原因で|によって)\s*([^\n。！？;；]{1,80})", re.I)
_FACT_LINE = re.compile(
    r"(?im)^\s*([A-Za-z_][A-Za-z0-9_ .-]{0,48})\s*[:=]\s*"
    r"([^\n]{1,120})\s*$"
)


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _safe_eval(node.operand)
        return +value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        a, b = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Add):
            out = a + b
        elif isinstance(node.op, ast.Sub):
            out = a - b
        elif isinstance(node.op, ast.Mult):
            out = a * b
        elif isinstance(node.op, ast.Div):
            out = a / b
        elif isinstance(node.op, ast.FloorDiv):
            out = a // b
        elif isinstance(node.op, ast.Mod):
            out = a % b
        elif isinstance(node.op, ast.Pow):
            if abs(float(b)) > 12:
                raise ValueError("exponent too large")
            out = a ** b
        else:
            raise ValueError("operator not allowed")
        if not math.isfinite(float(out)) or abs(float(out)) > 1e18:
            raise ValueError("result out of range")
        return out
    raise ValueError("unsupported expression")


class MultiStepMathExplorer:
    def run(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "").replace("×", "*").replace("÷", "/").replace("^", "**")
        if not _MATH_TRIGGER.search(raw):
            return None
        chunks: list[str] = []
        for chunk in _EXPR_CHUNK.findall(raw):
            expr = chunk.strip()
            if not re.search(r"\d", expr) or not re.search(r"(?:\*\*|[+\-*/%])", expr):
                continue
            if expr not in chunks:
                chunks.append(expr)
        if len(chunks) < 2:
            return None
        rows: list[tuple[str, float | int]] = []
        for expr in chunks[:8]:
            try:
                rows.append((expr, _safe_eval(ast.parse(expr, mode="eval"))))
            except Exception:
                continue
        if len(rows) < 2:
            return None
        reply = " / ".join(f"{expr} = {value}" for expr, value in rows)
        return {
            "ok": True,
            "reply": "多段算術を独立検証しました: " + reply,
            "confidence": 0.995,
            "verified": True,
            "grounded": True,
            "local": True,
            "multi_step_math_verified": True,
            "branches": [{"expr": expr, "value": value} for expr, value in rows],
            "decision_source": "verified_multi_step_math",
        }


class PythonRepairExplorer:
    def run(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "")
        block = _CODE_BLOCK.search(raw)
        if not block:
            return None
        source = block.group(1)
        try:
            ast.parse(source)
            return None
        except SyntaxError as original:
            pass

        variants: list[tuple[str, str]] = []
        lines = source.splitlines()
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if re.match(r"^\s*(def|class|if|elif|else|for|while|try|except|finally|with)\b", stripped) and not stripped.endswith(":"):
                fixed = list(lines)
                fixed[i] = stripped + ":"
                variants.append(("append_colon", "\n".join(fixed) + ("\n" if source.endswith("\n") else "")))
        variants.append(("repair_empty_parameter_list", re.sub(r"(def\s+[A-Za-z_]\w*)\s*\(\s*:", r"\1():", source)))

        for repair, candidate in variants[:6]:
            if candidate == source:
                continue
            try:
                ast.parse(candidate)
            except SyntaxError:
                continue
            return {
                "ok": True,
                "reply": "Python修復候補を静的検証しました。\n" + candidate.rstrip(),
                "confidence": 0.94,
                "verified": True,
                "grounded": True,
                "local": True,
                "python_repair_verified_syntax": True,
                "repair_kind": repair,
                "repaired_source": candidate,
                "original_syntax_error": f"line={original.lineno}:{original.msg}",
                "decision_source": "verified_python_syntax_repair",
            }
        return None


@dataclass(frozen=True)
class CausalEdge:
    source: str
    target: str


class CausalGraphExplorer:
    def run(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "")
        edges: list[CausalEdge] = []
        for a, b in _CAUSAL_ARROW.findall(raw):
            source = re.sub(r"\s+", " ", a).strip(" ,、")
            target = re.sub(r"\s+", " ", b).strip(" ,、")
            if source and target and source != target:
                edge = CausalEdge(source, target)
                if edge not in edges:
                    edges.append(edge)
        if len(edges) < 2:
            return None
        inferred: list[tuple[str, str, str]] = []
        for a in edges:
            for b in edges:
                if a.target == b.source and a.source != b.target:
                    inferred.append((a.source, a.target, b.target))
        if not inferred:
            return None
        rows = [f"{a} → {mid} → {c}" for a, mid, c in inferred[:8]]
        return {
            "ok": True,
            "reply": "明示された因果関係から連鎖候補を抽出しました: " + " / ".join(rows) + "。これは記述された辺からの到達関係で、現実の因果を独立に証明するものではありません。",
            "confidence": 0.72,
            "verified": False,
            "grounded": True,
            "local": True,
            "causal_graph_exploration": True,
            "edges": [{"source": x.source, "target": x.target} for x in edges],
            "paths": [{"source": a, "via": mid, "target": c} for a, mid, c in inferred[:8]],
        }


class CounterexampleConditionExplorer:
    def run(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "").strip()
        if not raw or not _COUNTER_CUE.search(raw):
            return None
        claims = [x.strip() for x in re.split(r"[\n。！？!?;；]+", raw) if _COUNTER_CUE.search(x)]
        if not claims:
            return None
        rows = ["「" + claim[:180] + "」は、主張が成立しない単一事例が見つかれば反証できます。" for claim in claims[:6]]
        return {
            "ok": True,
            "reply": "反例探索条件: " + " ".join(rows),
            "confidence": 0.62,
            "verified": False,
            "grounded": True,
            "local": True,
            "counterexample_exploration": True,
            "claims_examined": len(rows),
        }


class LongFormContradictionExplorer:
    NEG = re.compile(r"^(?:not\s+|no\s+|false\s*$|off\s*$|disabled\s*$|禁止|不要|使わない|しない)", re.I)
    POS = re.compile(r"^(?:yes\s*$|true\s*$|on\s*$|enabled\s*$|必要|必須|使う|する)", re.I)

    def run(self, text: str, history: list[Mapping[str, Any]] | None = None) -> dict[str, Any] | None:
        corpus: list[str] = []
        for row in list(history or [])[-16:]:
            if str(row.get("role") or "") in {"user", "assistant"}:
                corpus.append(str(row.get("text") or ""))
        corpus.append(str(text or ""))

        values: dict[str, set[str]] = {}
        for chunk in corpus:
            for key, raw in _FACT_LINE.findall(chunk):
                k = re.sub(r"\s+", " ", key.strip().casefold())
                v = re.sub(r"\s+", " ", raw.strip().casefold())
                values.setdefault(k, set()).add(v)

        conflicts: list[tuple[str, list[str]]] = []
        for key, rows in values.items():
            if len(rows) < 2:
                continue
            positive = any(self.POS.search(v) for v in rows)
            negative = any(self.NEG.search(v) for v in rows)
            if positive and negative:
                conflicts.append((key, sorted(rows)))
                continue
            if all(len(v) <= 40 for v in rows):
                conflicts.append((key, sorted(rows)))

        if not conflicts:
            return None
        rendered = [f"{key} => {', '.join(vals[:4])}" for key, vals in conflicts[:8]]
        return {
            "ok": True,
            "reply": "長文整合性チェックで競合する割当を検出しました: " + " / ".join(rendered),
            "confidence": 0.96,
            "verified": True,
            "grounded": True,
            "local": True,
            "longform_contradiction_verified": True,
            "conflicts": [{"key": key, "values": vals[:4]} for key, vals in conflicts[:8]],
            "decision_source": "verified_longform_assignment_conflict",
        }
