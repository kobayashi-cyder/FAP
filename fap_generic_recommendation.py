from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RecommendationAction:
    action_id: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationDomain:
    domain_id: str
    title: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationContext:
    context_id: str
    domain_id: str
    label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationPreference:
    preference_id: str
    label: str
    aliases: tuple[str, ...]
    add_tags: tuple[str, ...]
    remove_tags: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationSignal:
    signal_id: str
    label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationItem:
    item_id: str
    domain_id: str
    name: str
    contexts: tuple[str, ...]
    tags: tuple[str, ...]
    excluded_by: tuple[str, ...]
    base_score: float
    reason: str


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def _compact(text: str) -> str:
    return re.sub(r"[\s\-‐‑–—_・･、。，．,:：;；!?！？'\"]+", "", _norm(text))


def _alias_hits(text: str, aliases: Sequence[str]) -> list[str]:
    value = _compact(text)
    found: list[str] = []
    for alias in aliases:
        token = _compact(alias)
        if token and token in value:
            found.append(alias)
    return found


class GenericRecommendationEngine:
    """Data-driven multi-turn recommendation engine.

    The Python layer knows only generic concepts: action, domain, context,
    preferences, constraints and scored candidates. Concrete recommendation
    vocabulary and candidates live in knowledge/*.jsonl. A follow-up turn is
    accepted only when recent user history contains a matching recommendation
    request, preventing unrelated statements from being hijacked.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.actions: tuple[RecommendationAction, ...] = ()
        self.domains: tuple[RecommendationDomain, ...] = ()
        self.contexts: tuple[RecommendationContext, ...] = ()
        self.preferences: tuple[RecommendationPreference, ...] = ()
        self.signals: tuple[RecommendationSignal, ...] = ()
        self.items: tuple[RecommendationItem, ...] = ()
        self._load()

    def _load(self) -> None:
        actions: list[RecommendationAction] = []
        domains: list[RecommendationDomain] = []
        contexts: list[RecommendationContext] = []
        preferences: list[RecommendationPreference] = []
        signals: list[RecommendationSignal] = []
        items: list[RecommendationItem] = []

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
                if kind == "recommendation_action":
                    aid = str(row.get("id") or "").strip()
                    if aid:
                        actions.append(RecommendationAction(
                            aid,
                            tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        ))
                elif kind == "recommendation_domain":
                    did = str(row.get("id") or "").strip()
                    if did:
                        domains.append(RecommendationDomain(
                            did,
                            str(row.get("title") or did),
                            tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        ))
                elif kind == "recommendation_context":
                    cid = str(row.get("id") or "").strip()
                    did = str(row.get("domain") or "").strip()
                    if cid and did:
                        contexts.append(RecommendationContext(
                            cid,
                            did,
                            str(row.get("label") or cid),
                            tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        ))
                elif kind == "recommendation_preference":
                    pid = str(row.get("id") or "").strip()
                    if pid:
                        preferences.append(RecommendationPreference(
                            pid,
                            str(row.get("label") or pid),
                            tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                            tuple(str(x) for x in (row.get("add_tags") or []) if str(x).strip()),
                            tuple(str(x) for x in (row.get("remove_tags") or []) if str(x).strip()),
                        ))
                elif kind == "recommendation_signal":
                    sid = str(row.get("id") or "").strip()
                    if sid:
                        signals.append(RecommendationSignal(
                            sid,
                            str(row.get("label") or sid),
                            tuple(str(x) for x in (row.get("aliases") or []) if str(x).strip()),
                        ))
                elif kind == "recommendation_item":
                    iid = str(row.get("id") or "").strip()
                    did = str(row.get("domain") or "").strip()
                    name = str(row.get("name") or "").strip()
                    if iid and did and name:
                        try:
                            base_score = float(row.get("base_score", 0.5))
                        except Exception:
                            base_score = 0.5
                        items.append(RecommendationItem(
                            iid,
                            did,
                            name,
                            tuple(str(x) for x in (row.get("contexts") or []) if str(x).strip()),
                            tuple(str(x) for x in (row.get("tags") or []) if str(x).strip()),
                            tuple(str(x) for x in (row.get("excluded_by") or []) if str(x).strip()),
                            base_score,
                            str(row.get("reason") or "").strip(),
                        ))

        self.actions = tuple(actions)
        self.domains = tuple(domains)
        self.contexts = tuple(contexts)
        self.preferences = tuple(preferences)
        self.signals = tuple(signals)
        self.items = tuple(items)

    @staticmethod
    def _best_alias(text: str, rows, attr: str = "aliases"):
        ranked = []
        for row in rows:
            hits = _alias_hits(text, getattr(row, attr))
            if hits:
                score = len(hits) + max(len(_compact(x)) for x in hits) / 20.0
                ranked.append((score, row, hits))
        ranked.sort(key=lambda x: (-x[0], str(getattr(x[1], "domain_id", getattr(x[1], "action_id", "")))))
        return ranked[0] if ranked else None

    def _action(self, text: str):
        return self._best_alias(text, self.actions)

    def _domain(self, text: str):
        return self._best_alias(text, self.domains)

    def _context(self, text: str, domain_id: str) -> RecommendationContext | None:
        rows = [x for x in self.contexts if x.domain_id == domain_id]
        hit = self._best_alias(text, rows)
        return hit[1] if hit else None

    def _parse_preferences(self, texts: Sequence[str]) -> tuple[set[str], set[str], list[str]]:
        positive: set[str] = set()
        negative: set[str] = set()
        labels: list[str] = []
        merged = " ".join(str(x) for x in texts)
        for pref in self.preferences:
            if _alias_hits(merged, pref.aliases):
                positive.update(pref.add_tags)
                negative.update(pref.remove_tags)
                labels.append(pref.label)
        return positive, negative, labels

    def _parse_signals(self, texts: Sequence[str]) -> list[RecommendationSignal]:
        merged = " ".join(str(x) for x in texts)
        return [signal for signal in self.signals if _alias_hits(merged, signal.aliases)]

    def _active_request(self, history: list[Mapping]) -> tuple[int, RecommendationDomain, RecommendationContext | None] | None:
        for idx in range(len(history) - 1, -1, -1):
            row = history[idx]
            if row.get("role") != "user":
                continue
            text = str(row.get("text", ""))
            action = self._action(text)
            domain_hit = self._domain(text)
            if action and domain_hit:
                domain = domain_hit[1]
                return idx, domain, self._context(text, domain.domain_id)
        return None

    def _constraints_present(self, text: str) -> bool:
        if self._parse_signals([text]):
            return True
        positive, negative, _ = self._parse_preferences([text])
        return bool(positive or negative)

    def _rank_items(
        self,
        domain: RecommendationDomain,
        context: RecommendationContext | None,
        positive: set[str],
        negative: set[str],
    ) -> list[tuple[float, RecommendationItem, list[str]]]:
        ranked: list[tuple[float, RecommendationItem, list[str]]] = []
        for item in self.items:
            if item.domain_id != domain.domain_id:
                continue
            if set(item.excluded_by) & positive:
                continue
            score = item.base_score
            reasons: list[str] = []
            if context and context.context_id in item.contexts:
                score += 1.0
                reasons.append(context.label)
            matched = sorted(set(item.tags) & positive)
            score += 0.8 * len(matched)
            if matched:
                reasons.extend(matched)
            conflicts = set(item.tags) & negative
            score -= 1.0 * len(conflicts)
            ranked.append((score, item, reasons))
        ranked.sort(key=lambda x: (-x[0], x[1].item_id))
        return ranked

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        current = str(text or "").strip()
        if not current:
            return None

        action = self._action(current)
        domain_hit = self._domain(current)
        direct_request = bool(action and domain_hit)

        active = None if direct_request else self._active_request(history)
        if not direct_request:
            if active is None or not self._constraints_present(current):
                return None
            start_idx, domain, context = active
            user_texts = [
                str(row.get("text", ""))
                for row in history[start_idx:]
                if row.get("role") == "user"
            ] + [current]
            followup = True
        else:
            domain = domain_hit[1]
            context = self._context(current, domain.domain_id)
            user_texts = [current]
            followup = False

        positive, negative, preference_labels = self._parse_preferences(user_texts)
        signals = self._parse_signals(user_texts)
        ranked = self._rank_items(domain, context, positive, negative)
        if not ranked:
            return {
                "ok": False,
                "reply": "条件に合うローカル候補を見つけられませんでした。条件を少し緩めるか、別の候補軸を指定してください。",
                "confidence": 0.72,
                "needs_teacher": False,
                "recommendation_reasoning": True,
                "recommendation_verified": False,
                "candidate_ids": [],
                "domain_id": domain.domain_id,
                "route_tags": ["recommendation-intent", "constraint-compose", "candidate-rank"],
            }

        top = ranked[:3]
        lead = "条件を反映して候補を更新します。" if followup else "条件に合う候補を挙げます。"
        signal_labels = [s.label for s in signals]
        constraint_labels = list(dict.fromkeys(signal_labels + preference_labels))
        if constraint_labels:
            lead += " 反映条件: " + " / ".join(constraint_labels) + "。"
        elif not followup:
            lead += " まだ条件が少ないため、汎用的に選びやすい候補を優先しています。"

        lines = [lead]
        for idx, (_, item, matched) in enumerate(top, 1):
            detail = item.reason or ("適合タグ: " + ", ".join(matched) if matched else "汎用候補")
            lines.append(f"{idx}. {item.name} — {detail}")

        if not preference_labels:
            lines.append("量・予算感・和洋・温冷・手早さなどを指定すると、同じ仕組みでさらに絞れます。")

        return {
            "ok": True,
            "reply": "\n".join(lines),
            "confidence": 0.92 if followup else 0.88,
            "needs_teacher": False,
            "local": True,
            "grounded": True,
            "recommendation_reasoning": True,
            "recommendation_verified": True,
            "domain_id": domain.domain_id,
            "context_id": context.context_id if context else "",
            "contextual_followup": followup,
            "candidate_ids": [item.item_id for _, item, _ in top],
            "preference_labels": preference_labels,
            "signal_labels": signal_labels,
            "route_tags": [
                "recommendation-intent",
                "recommendation-domain",
                "conversation-constraint-compose" if followup else "current-turn-constraints",
                "candidate-rank",
                "recommendation-verify",
            ],
        }
