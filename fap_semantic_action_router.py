from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SemanticResource:
    resource_id: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SemanticAction:
    action_id: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SemanticActionRule:
    rule_id: str
    resource_id: str
    action_id: str
    route: str


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def _compact(text: str) -> str:
    return re.sub(r"[\s\-‐‑–—_・･、。，．,:：;；!?！？'\"]+", "", _norm(text))


def _routing_window(text: str, max_chars: int = 1200) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    head = value.split("\n\n", 1)[0].strip()
    if head and len(head) <= max_chars:
        return head
    return value[:max_chars]


def _hits(text: str, aliases: Sequence[str]) -> list[str]:
    value = _compact(text)
    out: list[str] = []
    for alias in aliases:
        token = _compact(alias)
        if token and token in value:
            out.append(alias)
    return out


class SemanticActionRouter:
    """Data-driven action/resource intent composition.

    The code has no subject-specific branches. Concrete language for resources
    (image, audio, etc.) and actions (create, inspect, explain, etc.) is loaded
    from JSONL. A route is selected only when both semantic dimensions match.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.resources: tuple[SemanticResource, ...] = ()
        self.actions: tuple[SemanticAction, ...] = ()
        self.rules: tuple[SemanticActionRule, ...] = ()
        self._load()

    def _load(self) -> None:
        resources: list[SemanticResource] = []
        actions: list[SemanticAction] = []
        rules: list[SemanticActionRule] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            return
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                kind = str(row.get("kind") or "")
                if kind == "semantic_resource":
                    rid = str(row.get("id") or "").strip()
                    aliases = tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip())
                    if rid and aliases:
                        resources.append(SemanticResource(rid, aliases))
                elif kind == "semantic_action":
                    aid = str(row.get("id") or "").strip()
                    aliases = tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip())
                    if aid and aliases:
                        actions.append(SemanticAction(aid, aliases))
                elif kind == "semantic_action_rule":
                    rule_id = str(row.get("id") or "").strip()
                    resource_id = str(row.get("resource") or "").strip()
                    action_id = str(row.get("action") or "").strip()
                    route = str(row.get("route") or "").strip()
                    if rule_id and resource_id and action_id and route:
                        rules.append(SemanticActionRule(rule_id, resource_id, action_id, route))
        self.resources = tuple(resources)
        self.actions = tuple(actions)
        self.rules = tuple(rules)

    @staticmethod
    def _best(text: str, rows):
        ranked = []
        for row in rows:
            hits = _hits(text, row.aliases)
            if not hits:
                continue
            score = 2.0 * len(hits) + max(len(_compact(x)) for x in hits) / 20.0
            ranked.append((score, row, hits))
        ranked.sort(key=lambda x: (-x[0], getattr(x[1], "resource_id", getattr(x[1], "action_id", ""))))
        return ranked[0] if ranked else None

    def match(self, text: str) -> dict | None:
        route_text = _routing_window(text)
        resource_hit = self._best(route_text, self.resources)
        action_hit = self._best(route_text, self.actions)
        if resource_hit is None or action_hit is None:
            return None
        resource = resource_hit[1]
        action = action_hit[1]
        for rule in self.rules:
            if rule.resource_id == resource.resource_id and rule.action_id == action.action_id:
                return {
                    "rule_id": rule.rule_id,
                    "resource_id": resource.resource_id,
                    "action_id": action.action_id,
                    "route": rule.route,
                    "resource_hits": resource_hit[2],
                    "action_hits": action_hit[2],
                    "score": round(resource_hit[0] + action_hit[0], 4),
                }
        return None
