from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ConversationIntent:
    intent_id: str
    subject_aliases: tuple[str, ...]
    action_aliases: tuple[str, ...]
    min_subject_hits: int = 1
    min_action_hits: int = 1
    response_mode: str = ""


@dataclass(frozen=True)
class CapabilityGroup:
    group_id: str
    label: str
    matches: tuple[str, ...]


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
    found: list[str] = []
    for alias in aliases:
        token = _compact(alias)
        if token and token in value:
            found.append(alias)
    return found


def _nonnegative_int(value: object, default: int = 1) -> int:
    """Parse optional knowledge-data thresholds without letting one bad row abort loading."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return max(0, int(default))


def _safe_int(value: object, default: int = 0) -> int:
    """Render runtime counters defensively when status data is partial or malformed."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)


class SemanticConversationRouter:
    """Small data-driven semantic intent router for ordinary conversation.

    Utterance-specific branches live neither here nor in the gateway. Intent
    definitions are loaded from JSONL and matched compositionally from subject
    and action concepts. This makes paraphrases share one route.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.intents: tuple[ConversationIntent, ...] = ()
        self.groups: tuple[CapabilityGroup, ...] = ()
        self._load()

    def _load(self) -> None:
        intents: list[ConversationIntent] = []
        groups: list[CapabilityGroup] = []
        folder = self.root / "knowledge"
        if not folder.exists():
            self.intents = ()
            self.groups = ()
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
                if kind == "conversation_intent":
                    iid = str(row.get("id") or "").strip()
                    if not iid:
                        continue
                    intents.append(ConversationIntent(
                        intent_id=iid,
                        subject_aliases=tuple(str(x) for x in (row.get("subject_aliases") or []) if str(x).strip()),
                        action_aliases=tuple(str(x) for x in (row.get("action_aliases") or []) if str(x).strip()),
                        min_subject_hits=_nonnegative_int(row.get("min_subject_hits", 1), 1),
                        min_action_hits=_nonnegative_int(row.get("min_action_hits", 1), 1),
                        response_mode=str(row.get("response_mode") or iid),
                    ))
                elif kind == "capability_group":
                    gid = str(row.get("id") or "").strip()
                    if not gid:
                        continue
                    groups.append(CapabilityGroup(
                        group_id=gid,
                        label=str(row.get("label") or gid),
                        matches=tuple(str(x).lower() for x in (row.get("matches") or []) if str(x).strip()),
                    ))

        self.intents = tuple(intents)
        self.groups = tuple(groups)

    def match(self, text: str) -> dict | None:
        value = str(text or "").strip()
        if not value:
            return None
        route_text = _routing_window(value)
        ranked: list[tuple[float, ConversationIntent, list[str], list[str]]] = []
        for intent in self.intents:
            subjects = _hits(route_text, intent.subject_aliases)
            actions = _hits(route_text, intent.action_aliases)
            if len(subjects) < intent.min_subject_hits or len(actions) < intent.min_action_hits:
                continue
            score = 2.0 * len(subjects) + 1.5 * len(actions)
            score += min(1.0, sum(len(_compact(x)) for x in subjects + actions) / 20.0)
            ranked.append((score, intent, subjects, actions))

        if not ranked:
            return None
        ranked.sort(key=lambda item: (-item[0], item[1].intent_id))
        score, intent, subjects, actions = ranked[0]
        return {
            "intent_id": intent.intent_id,
            "response_mode": intent.response_mode,
            "score": round(score, 4),
            "subject_hits": subjects,
            "action_hits": actions,
        }

    def group_capabilities(self, capabilities: Sequence[str]) -> list[dict]:
        caps = [str(x) for x in capabilities]
        rows: list[dict] = []
        used: set[str] = set()
        for group in self.groups:
            selected: list[str] = []
            for cap in caps:
                low = cap.lower()
                if any(token in low for token in group.matches):
                    selected.append(cap)
                    used.add(cap)
            if selected:
                rows.append({
                    "id": group.group_id,
                    "label": group.label,
                    "capabilities": selected,
                })
        extras = [cap for cap in caps if cap not in used]
        if extras:
            rows.append({"id": "other", "label": "その他", "capabilities": extras})
        return rows


class RuntimeSelfProfile:
    """Render self-description from current runtime state, not canned version text."""

    def __init__(self, router: SemanticConversationRouter):
        self.router = router

    @staticmethod
    def _select_examples(group: Mapping, limit: int = 4) -> list[str]:
        caps = [str(x) for x in group.get("capabilities", [])]
        latest = [x for x in caps if "latest-mainline-chat" in x]
        others = [x for x in caps if x not in latest]
        return (latest + others)[:limit]

    def render(self, *, version: str, capabilities: Sequence[str], status: Mapping) -> str:
        groups = self.router.group_capabilities(capabilities)
        lines = [
            f"FAP {version} です。",
            "現在の実装状態から自己紹介します。固定された旧バージョン説明ではなく、起動中の能力一覧を要約しています。",
        ]

        displayed = 0
        for group in groups:
            if group.get("id") == "other":
                continue
            examples = self._select_examples(group)
            if not examples:
                continue
            lines.append(f"- {group.get('label')}: " + " / ".join(examples))
            displayed += 1
            if displayed >= 6:
                break

        image = status.get("image_orchestrator") if isinstance(status, Mapping) else None
        if isinstance(image, Mapping):
            state = "接続済み" if image.get("generator_connected") else "未接続"
            lines.append(f"- 画像生成器: {state}")

        rule = status.get("generic_rule_reasoner") if isinstance(status, Mapping) else None
        if isinstance(rule, Mapping):
            lines.append(
                f"- 汎用ルール推論: entities={_safe_int(rule.get('entities', 0))}, "
                f"relations={_safe_int(rule.get('relations', 0))}, rules={_safe_int(rule.get('rules', 0))}"
            )

        derivation = status.get("generic_derivation") if isinstance(status, Mapping) else None
        if isinstance(derivation, Mapping):
            lines.append(f"- 汎用記号導出: records={_safe_int(derivation.get('records', 0))}")

        return "\n".join(lines)

    def run(self, text: str, *, version: str, capabilities: Sequence[str], status: Mapping) -> dict | None:
        match = self.router.match(text)
        if match is None:
            return None

        mode = str(match.get("response_mode") or "")
        if mode == "runtime_greeting":
            reply = f"こんにちは。FAP {version} は稼働中です。現在の実装状態に基づいて応答します。"
            route_tags = [
                "semantic-conversation-intent",
                "runtime-self-inspect",
                "dynamic-greeting",
            ]
        elif mode == "runtime_self_profile":
            reply = self.render(version=version, capabilities=capabilities, status=status)
            route_tags = [
                "semantic-conversation-intent",
                "runtime-self-inspect",
                "capability-group",
                "dynamic-self-profile",
            ]
        else:
            return None

        return {
            "ok": True,
            "reply": reply,
            "confidence": min(0.99, 0.90 + float(match.get("score", 0.0)) / 100.0),
            "needs_teacher": False,
            "local": True,
            "self_capability": True,
            "semantic_conversation": True,
            "semantic_intent": match.get("intent_id"),
            "semantic_match": match,
            "route_tags": route_tags,
        }
