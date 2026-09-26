from __future__ import annotations

import ast
import json
import operator
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SemanticEntity:
    entity_id: str
    aliases: tuple[str, ...]
    types: tuple[str, ...]
    properties: Mapping[str, float]
    title: str


@dataclass(frozen=True)
class SemanticRelation:
    relation_id: str
    aliases: tuple[str, ...]
    unit: str
    label: str


@dataclass(frozen=True)
class SemanticConstant:
    constant_id: str
    value: float
    unit: str
    reason: str


@dataclass(frozen=True)
class SemanticRule:
    rule_id: str
    relation: str
    subject_type: str
    requires: tuple[str, ...]
    expression: str
    label: str
    explanation: str


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def _compact(text: str) -> str:
    return re.sub(r"[\s\-‐‑–—_・･、。，．,:：;；!?！？'\"]+", "", _norm(text))


def _safe_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric value required")
    return float(value)


def _eval_expr(expr: str, env: Mapping[str, float]) -> float:
    tree = ast.parse(str(expr), mode="eval")

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            return _safe_number(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise KeyError(node.id)
            return _safe_number(env[node.id])
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
            return _ALLOWED_UNARY[type(node.op)](walk(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 8 or abs(left) > 1e9):
                raise ValueError("power outside safety bound")
            value = _ALLOWED_BINOPS[type(node.op)](left, right)
            if abs(value) > 1e15:
                raise ValueError("result outside safety bound")
            return float(value)
        raise ValueError(f"unsupported expression syntax: {type(node).__name__}")

    return walk(tree.body)


def _display_number(value: float) -> str:
    rounded = round(float(value))
    if abs(float(value) - rounded) < 1e-10:
        return str(int(rounded))
    return f"{float(value):.10g}"


class GenericRuleReasoner:
    """Domain-neutral semantic rule engine.

    The Python code contains no theorem names or answer table. Subject aliases,
    relation aliases, constants and derivation rules are loaded from JSONL data.
    Rules can depend on entity properties, constants, or other derived
    relations, so answers are obtained by recursive rule chaining rather than
    exact question-response matching.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.entities: tuple[SemanticEntity, ...] = ()
        self.relations: tuple[SemanticRelation, ...] = ()
        self.constants: dict[str, SemanticConstant] = {}
        self.rules: tuple[SemanticRule, ...] = ()
        self._load()

    def _load(self) -> None:
        entities: list[SemanticEntity] = []
        relations: list[SemanticRelation] = []
        constants: dict[str, SemanticConstant] = {}
        rules: list[SemanticRule] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            return

        for path in sorted(folder.rglob("*.jsonl")):
            try:
                rows = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in rows:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                kind = row.get("kind")
                if kind == "semantic_entity":
                    props = {}
                    for key, value in (row.get("properties") or {}).items():
                        try:
                            props[str(key)] = float(value)
                        except Exception:
                            pass
                    entities.append(SemanticEntity(
                        entity_id=str(row.get("id") or ""),
                        aliases=tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        types=tuple(str(x) for x in (row.get("types") or []) if str(x).strip()),
                        properties=props,
                        title=str(row.get("title") or row.get("id") or ""),
                    ))
                elif kind == "semantic_relation":
                    relations.append(SemanticRelation(
                        relation_id=str(row.get("id") or ""),
                        aliases=tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        unit=str(row.get("unit") or ""),
                        label=str(row.get("label") or row.get("id") or ""),
                    ))
                elif kind == "semantic_constant":
                    try:
                        value = float(row.get("value"))
                    except Exception:
                        continue
                    cid = str(row.get("id") or "")
                    if cid:
                        constants[cid] = SemanticConstant(
                            constant_id=cid,
                            value=value,
                            unit=str(row.get("unit") or ""),
                            reason=str(row.get("reason") or ""),
                        )
                elif kind == "semantic_rule":
                    rid = str(row.get("id") or "")
                    relation = str(row.get("relation") or "")
                    expression = str(row.get("expression") or "")
                    if rid and relation and expression:
                        rules.append(SemanticRule(
                            rule_id=rid,
                            relation=relation,
                            subject_type=str(row.get("subject_type") or ""),
                            requires=tuple(str(x) for x in (row.get("requires") or []) if str(x).strip()),
                            expression=expression,
                            label=str(row.get("label") or rid),
                            explanation=str(row.get("explanation") or ""),
                        ))

        self.entities = tuple(x for x in entities if x.entity_id)
        self.relations = tuple(x for x in relations if x.relation_id)
        self.constants = constants
        self.rules = tuple(rules)

    @staticmethod
    def _history_text(history: list[Mapping], limit: int = 10) -> str:
        rows: list[str] = []
        for row in history[-limit:]:
            if row.get("role") not in {"user", "assistant"}:
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if value:
                rows.append(value[:700])
        return "\n".join(rows)

    @staticmethod
    def _best_alias_match(text: str, aliases: tuple[str, ...]) -> float:
        n = _compact(text)
        best = 0.0
        for alias in aliases:
            a = _compact(alias)
            if not a:
                continue
            if a in n:
                best = max(best, 4.0 + min(4.0, len(a) / 4.0))
        return best

    def _resolve_relation(self, text: str) -> SemanticRelation | None:
        ranked = sorted(
            ((self._best_alias_match(text, rel.aliases), rel) for rel in self.relations),
            key=lambda item: (-item[0], item[1].relation_id),
        )
        return ranked[0][1] if ranked and ranked[0][0] > 0 else None

    def _resolve_entity(self, text: str, history: list[Mapping]) -> tuple[SemanticEntity | None, str]:
        direct = sorted(
            ((self._best_alias_match(text, ent.aliases), ent) for ent in self.entities),
            key=lambda item: (-item[0], item[1].entity_id),
        )
        if direct and direct[0][0] > 0:
            return direct[0][1], "current-turn"

        # Prefer explicit subjects from user turns over assistant-generated
        # text. Otherwise a previous answer can inject a different entity and
        # hijack a subjectless follow-up.
        for row in reversed(history[-10:]):
            if row.get("role") != "user":
                continue
            value = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
            if not value:
                continue
            ranked = sorted(
                ((self._best_alias_match(value, ent.aliases), ent) for ent in self.entities),
                key=lambda item: (-item[0], item[1].entity_id),
            )
            if ranked and ranked[0][0] > 0:
                return ranked[0][1], "conversation-context"

        # Assistant context is a last-resort continuity hint only when no user
        # turn contains an explicit known entity.
        assistant_context = "\n".join(
            re.sub(r"\s+", " ", str(row.get("text", ""))).strip()[:700]
            for row in history[-6:]
            if row.get("role") == "assistant" and str(row.get("text", "")).strip()
        )
        if assistant_context:
            historical = sorted(
                ((self._best_alias_match(assistant_context, ent.aliases), ent) for ent in self.entities),
                key=lambda item: (-item[0], item[1].entity_id),
            )
            if historical and historical[0][0] > 0:
                return historical[0][1], "conversation-context"
        return None, ""

    def _rules_for(self, relation_id: str, entity: SemanticEntity) -> list[SemanticRule]:
        return [
            rule for rule in self.rules
            if rule.relation == relation_id and (
                not rule.subject_type or rule.subject_type in entity.types
            )
        ]

    def _derive(
        self,
        entity: SemanticEntity,
        relation_id: str,
        stack: tuple[str, ...] = (),
    ) -> tuple[float, list[dict[str, Any]], list[str]] | None:
        if relation_id in stack or len(stack) >= 12:
            return None

        if relation_id in entity.properties:
            value = float(entity.properties[relation_id])
            return value, [{
                "kind": "property",
                "id": f"{entity.entity_id}.{relation_id}",
                "value": value,
            }], [f"{entity.title} の既知属性 {relation_id} = {_display_number(value)}"]

        if relation_id in self.constants:
            constant = self.constants[relation_id]
            reason = constant.reason or f"{constant.constant_id} = {_display_number(constant.value)}"
            return constant.value, [{
                "kind": "constant",
                "id": constant.constant_id,
                "value": constant.value,
            }], [reason]

        for rule in self._rules_for(relation_id, entity):
            env: dict[str, float] = {}
            evidence: list[dict[str, Any]] = []
            steps: list[str] = []
            failed = False
            for requirement in rule.requires:
                got = self._derive(entity, requirement, stack + (relation_id,))
                if got is None:
                    failed = True
                    break
                value, child_evidence, child_steps = got
                env[requirement] = value
                evidence.extend(child_evidence)
                steps.extend(child_steps)
            if failed:
                continue
            try:
                value = _eval_expr(rule.expression, env)
            except Exception:
                continue
            evidence.append({
                "kind": "rule",
                "id": rule.rule_id,
                "relation": rule.relation,
                "expression": rule.expression,
            })
            explanation = rule.explanation.format(
                subject=entity.title,
                result=_display_number(value),
                **{k: _display_number(v) for k, v in env.items()},
            ) if rule.explanation else f"{rule.label}: {rule.expression}"
            steps.append(explanation)
            return value, evidence, steps
        return None

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        query = str(text or "").strip()
        if not query:
            return None
        relation = self._resolve_relation(query)
        if relation is None:
            return None
        entity, context_source = self._resolve_entity(query, history)
        if entity is None:
            return None

        derived = self._derive(entity, relation.relation_id)
        if derived is None:
            return None
        value, evidence, steps = derived
        rendered = _display_number(value)
        unit = relation.unit
        answer_value = f"{rendered}{unit}" if unit else rendered

        compact_steps: list[str] = []
        seen = set()
        for step in steps:
            s = re.sub(r"\s+", " ", str(step)).strip()
            if s and s not in seen:
                seen.add(s)
                compact_steps.append(s)

        reply_lines = [f"{entity.title}の{relation.label}は {answer_value} です。"]
        if compact_steps:
            reply_lines.append("導出:")
            reply_lines.extend(f"- {step}" for step in compact_steps)

        return {
            "ok": True,
            "reply": "\n".join(reply_lines),
            "confidence": 0.96 if context_source == "current-turn" else 0.93,
            "needs_teacher": False,
            "local": True,
            "grounded": True,
            "rule_reasoning": True,
            "rule_verified": True,
            "subject_id": entity.entity_id,
            "relation_id": relation.relation_id,
            "value": value,
            "unit": unit,
            "context_source": context_source,
            "evidence_ids": [str(item.get("id")) for item in evidence if item.get("id")],
            "rule_trace": evidence,
            "route_tags": [
                "semantic-relation-resolve",
                "context-subject-resolve",
                "recursive-rule-chain",
                "safe-expression-eval",
                "evidence-trace",
            ],
        }
