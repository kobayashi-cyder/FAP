from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


_WORD = re.compile(r"[A-Za-z0-9_]{2,}|[一-龥ぁ-んァ-ンー]{2,}")
_STOP = {
    "して", "ください", "について", "説明", "確認", "検証",
    "what", "about", "please", "explain", "verify",
}


def _safe_session(value: object) -> str:
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or "default"))[:80]
    return sid or "default"


def _feature_hashes(text: str) -> tuple[str, ...]:
    """Return opaque topic features without persisting raw conversation text."""
    value = str(text or "").casefold()
    tokens: set[str] = set()
    for token in _WORD.findall(value):
        if token in _STOP:
            continue
        if re.search(r"[一-龥ぁ-んァ-ンー]", token) and len(token) > 4:
            tokens.update(token[i : i + 2] for i in range(len(token) - 1))
        else:
            tokens.add(token)
    return tuple(sorted(
        hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        for token in tokens
    )[:48])


def _similarity(a: Sequence[str], b: Sequence[str]) -> float:
    x, y = set(a), set(b)
    if not x or not y:
        return 0.0
    common = len(x & y)
    if common == 0:
        return 0.0
    # Coverage of the smaller topic representation is more useful than pure
    # Jaccard for short follow-up questions.
    return common / max(1, min(len(x), len(y)))


class EpistemicConflictLedger:
    """Bounded conflict state kept separate from semantic/factual memory.

    Only opaque topic hashes and internal candidate source IDs are persisted.
    Raw user text and candidate prose are deliberately excluded.
    """

    CONTRACT = "fap.epistemic.conflict-ledger.v1"
    MAX_PER_SESSION = 64
    MAX_SESSIONS = 64

    def __init__(self, root: Path | None = None):
        self.root = Path(root).expanduser().resolve() if root is not None else None
        self.path = (
            self.root / "epistemic_conflicts.json"
            if self.root is not None
            else None
        )
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._seq = 0
        if self.path is not None:
            self._load()

    @property
    def persistent(self) -> bool:
        return self.path is not None

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, Mapping) or raw.get("contract") != self.CONTRACT:
            return
        sessions = raw.get("sessions")
        if not isinstance(sessions, Mapping):
            return
        for sid, rows in list(sessions.items())[: self.MAX_SESSIONS]:
            safe_sid = _safe_session(sid)
            if not isinstance(rows, list):
                continue
            clean: list[dict[str, Any]] = []
            for row in rows[-self.MAX_PER_SESSION :]:
                if not isinstance(row, Mapping):
                    continue
                topic = row.get("topic")
                sources = row.get("sources")
                if not isinstance(topic, list) or not isinstance(sources, list):
                    continue
                clean.append({
                    "id": str(row.get("id") or "")[:32],
                    "topic": [str(x)[:16] for x in topic[:48]],
                    "sources": [str(x)[:64] for x in sources[:4]],
                    "active": bool(row.get("active", True)),
                    "first_seq": max(0, int(row.get("first_seq", 0))),
                    "last_seq": max(0, int(row.get("last_seq", 0))),
                    "hits": max(1, int(row.get("hits", 1))),
                })
                self._seq = max(self._seq, clean[-1]["last_seq"])
            if clean:
                self._rows[safe_sid] = clean

    def _save(self) -> None:
        if self.path is None:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "contract": self.CONTRACT,
            "sessions": {
                sid: rows[-self.MAX_PER_SESSION :]
                for sid, rows in list(self._rows.items())[-self.MAX_SESSIONS :]
            },
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @staticmethod
    def _conflict_id(topic: Sequence[str], sources: Sequence[str]) -> str:
        raw = "|".join(sorted(topic)) + "::" + "|".join(sorted(sources))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def relevant(
        self,
        session_id: str,
        text: str,
        *,
        limit: int = 8,
        threshold: float = 0.34,
    ) -> list[dict[str, Any]]:
        sid = _safe_session(session_id)
        topic = _feature_hashes(text)
        if not topic:
            return []
        scored = []
        for row in self._rows.get(sid, ()):
            if not row.get("active"):
                continue
            score = _similarity(topic, row.get("topic") or ())
            if score < threshold:
                continue
            scored.append((score, row))
        scored.sort(key=lambda x: (-x[0], -int(x[1].get("last_seq", 0))))
        return [
            {
                "id": row["id"],
                "sources": list(row.get("sources") or ()),
                "score": round(score, 4),
                "hits": int(row.get("hits", 1)),
            }
            for score, row in scored[: max(1, min(16, int(limit)))]
        ]

    def _record(
        self,
        sid: str,
        topic: tuple[str, ...],
        sources: Sequence[str],
    ) -> str:
        source_list = sorted({str(x)[:64] for x in sources if str(x)})[:4]
        cid = self._conflict_id(topic, source_list)
        rows = self._rows.setdefault(sid, [])
        self._seq += 1
        for row in rows:
            if row.get("id") == cid:
                row["active"] = True
                row["last_seq"] = self._seq
                row["hits"] = int(row.get("hits", 1)) + 1
                return cid
        rows.append({
            "id": cid,
            "topic": list(topic),
            "sources": source_list,
            "active": True,
            "first_seq": self._seq,
            "last_seq": self._seq,
            "hits": 1,
        })
        if len(rows) > self.MAX_PER_SESSION:
            del rows[: len(rows) - self.MAX_PER_SESSION]
        return cid

    @staticmethod
    def _selected_verified(payload: Mapping[str, Any]) -> bool:
        execution = payload.get("response_series_execution")
        if not isinstance(execution, Mapping):
            return bool(
                payload.get("verified")
                or payload.get("factual_qa")
                or payload.get("rule_verified")
                or payload.get("derivation_verified")
            )
        selected = str(execution.get("selected") or "")
        rows = execution.get("candidates")
        if isinstance(rows, Sequence):
            for row in rows:
                if (
                    isinstance(row, Mapping)
                    and str(row.get("id") or "") == selected
                ):
                    return bool(row.get("verified"))
        return bool(payload.get("verified"))

    def observe(
        self,
        session_id: str,
        text: str,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        sid = _safe_session(session_id)
        data = dict(payload or {})
        topic = _feature_hashes(text)
        execution = data.get("response_series_execution")
        execution = execution if isinstance(execution, Mapping) else {}
        disagreements = execution.get("verified_disagreements")
        disagreements = disagreements if isinstance(disagreements, Sequence) else []

        recorded: list[str] = []
        for pair in disagreements[:8]:
            if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)):
                continue
            sources = [str(x) for x in list(pair)[:4]]
            if topic and len(sources) >= 2:
                recorded.append(self._record(sid, topic, sources))

        resolved: list[str] = []
        episode = data.get("reasoning_episode")
        episode_ok = (
            isinstance(episode, Mapping)
            and episode.get("verdict") == "OK"
        )
        if (
            not disagreements
            and episode_ok
            and self._selected_verified(data)
            and topic
        ):
            for row in self._rows.get(sid, ()):
                if not row.get("active"):
                    continue
                if _similarity(topic, row.get("topic") or ()) < 0.34:
                    continue
                row["active"] = False
                self._seq += 1
                row["last_seq"] = self._seq
                resolved.append(str(row.get("id") or ""))

        if recorded or resolved:
            self._save()

        active = sum(
            1
            for row in self._rows.get(sid, ())
            if row.get("active")
        )
        return {
            "contract": self.CONTRACT,
            "persistent": self.persistent,
            "recorded": list(dict.fromkeys(recorded)),
            "resolved": list(dict.fromkeys(resolved)),
            "active_count": active,
            "raw_text_persisted": False,
            "candidate_prose_persisted": False,
        }

    def snapshot(self, session_id: str) -> tuple[dict[str, Any], ...]:
        sid = _safe_session(session_id)
        return tuple({
            "id": str(row.get("id") or ""),
            "sources": tuple(row.get("sources") or ()),
            "active": bool(row.get("active")),
            "first_seq": int(row.get("first_seq", 0)),
            "last_seq": int(row.get("last_seq", 0)),
            "hits": int(row.get("hits", 1)),
            "topic_feature_count": len(row.get("topic") or ()),
        } for row in self._rows.get(sid, ()))

    def clear_session(self, session_id: str) -> None:
        self._rows.pop(_safe_session(session_id), None)
        self._save()

    def active_count(self) -> int:
        return sum(
            1
            for rows in self._rows.values()
            for row in rows
            if row.get("active")
        )
