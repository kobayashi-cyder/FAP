from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import threading
from pathlib import Path
from typing import Iterable

from fap_knowledge_retrieval import terms


NEGATION = re.compile(
    r"(ない|ません|ぬ|ではない|とは限らない|不可能|不可|否定|"
    r"\bnot\b|\bno\b|\bnever\b|\bwithout\b|\bimpossible\b)",
    re.I,
)
NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.I)

KIND_VALUE = {
    "falsify": 1.00,
    "uncertainty": 0.98,
    "failure": 0.96,
    "boundary": 0.94,
    "evidence": 0.93,
    "validation": 0.92,
    "alternative": 0.91,
    "mechanism": 0.90,
    "cause": 0.88,
    "dependency": 0.86,
    "sensitivity": 0.85,
    "assumption": 0.84,
    "counterfactual": 0.83,
    "prediction": 0.82,
    "error": 0.82,
    "interaction": 0.80,
    "conditions": 0.78,
    "observability": 0.77,
    "dominance": 0.76,
    "scale": 0.75,
    "components": 0.72,
    "decomposition": 0.72,
    "transfer": 0.70,
    "known": 0.66,
    "definition": 0.62,
    "live_data": 0.60,
}


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _jaccard(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def _numeric_signature(text: str) -> tuple[str, ...]:
    return tuple(NUMBER.findall(str(text or ""))[:12])


def _answer_similarity(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def _contradiction_reason(a: str, b: str) -> str:
    if not a or not b:
        return ""
    sim = _answer_similarity(a, b)
    neg_a = bool(NEGATION.search(a))
    neg_b = bool(NEGATION.search(b))
    if sim >= 0.30 and neg_a != neg_b:
        return "negation-polarity-mismatch"
    na = _numeric_signature(a)
    nb = _numeric_signature(b)
    if na and nb and na != nb and sim >= 0.18:
        return "numeric-mismatch"
    if sim < 0.12 and _jaccard(a, b) >= 0.35:
        return "low-answer-overlap"
    return ""


class QuestionValueScorer:
    """Ranks questions by epistemic value instead of raw count."""

    def score(self, question, prior_questions: Iterable, evidence_hint: float = 0.0) -> float:
        kind = str(getattr(question, "kind", ""))
        qtext = str(getattr(question, "question", ""))
        base = KIND_VALUE.get(kind, 0.68)

        max_sim = 0.0
        for prior in prior_questions:
            p = str(getattr(prior, "question", prior))
            max_sim = max(max_sim, _jaccard(qtext, p))
            if max_sim >= 0.98:
                break
        novelty = max(0.0, 1.0 - max_sim)

        generation = int(getattr(question, "generation", 0) or 0)
        depth_factor = 1.0 / (1.0 + 0.08 * max(0, generation))
        evidence_factor = min(1.0, max(0.0, float(evidence_hint)))

        # Critical/uncertainty questions get weight, but duplicates are strongly
        # suppressed. Evidence availability matters without making easy questions
        # dominate everything.
        value = (
            0.52 * base
            + 0.30 * novelty
            + 0.12 * evidence_factor
            + 0.06 * depth_factor
        )
        return round(max(0.0, min(1.0, value)), 4)

    def rank(self, questions: list, evidence_hint: float = 0.0) -> list:
        ranked = []
        accepted = []
        for q in questions:
            value = self.score(q, accepted, evidence_hint)
            setattr(q, "value_score", value)
            accepted.append(q)
            ranked.append(q)
        ranked.sort(
            key=lambda q: (
                -float(getattr(q, "value_score", 0.0)),
                int(getattr(q, "generation", 0) or 0),
                str(getattr(q, "qid", "")),
            )
        )
        return ranked


class EpistemicLedger:
    """Persistent, conservative store for verified inquiry outcomes.

    Entries retain their original evidence IDs. A stored conclusion is useful
    for recall, but it is not treated as new independent evidence. Contradictory
    conclusions are quarantined rather than silently overwriting one another.
    """

    VERSION = 1
    MAX_ENTRIES = 8000
    MAX_CONFLICTS = 2000
    MAX_FRONTIER = 4000

    def __init__(self, root: Path):
        self.dir = Path(root) / "runtime" / "epistemic"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "ledger.json"
        self._lock = threading.RLock()
        self._cache: dict | None = None

    def _blank(self) -> dict:
        return {
            "version": self.VERSION,
            "entries": [],
            "conflicts": [],
            "frontier": [],
            "stats": {
                "promotions": 0,
                "reinforcements": 0,
                "conflicts": 0,
            },
        }

    def _load(self) -> dict:
        with self._lock:
            if self._cache is not None:
                return self._cache
            if not self.path.exists():
                self._cache = self._blank()
                return self._cache
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("not an object")
            except Exception:
                data = self._blank()
            for key, default in (
                ("entries", []),
                ("conflicts", []),
                ("frontier", []),
                ("stats", {}),
            ):
                if key not in data or not isinstance(data[key], type(default)):
                    data[key] = default
            self._cache = data
            return data

    def _save(self) -> None:
        with self._lock:
            data = self._load()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            tmp.replace(self.path)

    @staticmethod
    def _entry_id(topic: str, question: str, answer: str) -> str:
        raw = f"{_norm(topic)}\n{_norm(question)}\n{_norm(answer)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:20]

    def recall(self, question: str, min_similarity: float = 0.76) -> dict | None:
        best = None
        best_score = 0.0
        for entry in self._load()["entries"]:
            score = _jaccard(question, str(entry.get("question", "")))
            if score > best_score:
                best_score = score
                best = entry
        if best is None or best_score < min_similarity:
            return None
        out = dict(best)
        out["recall_similarity"] = round(best_score, 4)
        return out

    def _find_similar(self, topic: str, question: str, threshold: float = 0.64) -> list[dict]:
        out = []
        for entry in self._load()["entries"]:
            qsim = _jaccard(question, str(entry.get("question", "")))
            tsim = _jaccard(topic, str(entry.get("topic", "")))
            score = max(qsim, 0.65 * qsim + 0.35 * tsim)
            if score >= threshold:
                out.append((score, entry))
        out.sort(key=lambda x: -x[0])
        return [e for _, e in out[:12]]

    def promote(
        self,
        *,
        topic: str,
        kind: str,
        question: str,
        answer: str,
        evidence_ids: Iterable[str],
        value_score: float,
        confidence: float,
    ) -> dict:
        evidence = tuple(dict.fromkeys(str(x) for x in evidence_ids if str(x)))
        # Japanese factual conclusions can be short but still complete. Use a
        # small minimum while keeping evidence and value gates mandatory.
        if not evidence or len(str(answer).strip()) < 8 or float(value_score) < 0.45:
            return {"status": "skipped", "reason": "promotion-gate"}

        with self._lock:
            data = self._load()
            similar = self._find_similar(topic, question)

            for existing in similar:
                reason = _contradiction_reason(str(existing.get("answer", "")), answer)
                if reason:
                    conflict = {
                        "ts": _now(),
                        "topic": topic,
                        "question": question,
                        "new_answer": answer,
                        "existing_id": existing.get("id"),
                        "existing_answer": existing.get("answer", ""),
                        "reason": reason,
                        "evidence_ids": list(evidence),
                    }
                    sig = self._entry_id(topic, question, reason + answer)
                    if not any(x.get("signature") == sig for x in data["conflicts"]):
                        conflict["signature"] = sig
                        data["conflicts"].append(conflict)
                        data["conflicts"] = data["conflicts"][-self.MAX_CONFLICTS:]
                        data["stats"]["conflicts"] = int(data["stats"].get("conflicts", 0)) + 1
                        self._save()
                    return {"status": "conflict", "reason": reason, "existing_id": existing.get("id")}

            # Reinforce a semantically equivalent stored conclusion rather than
            # duplicating it.
            for existing in similar:
                if _answer_similarity(str(existing.get("answer", "")), answer) >= 0.52:
                    existing["support"] = int(existing.get("support", 1)) + 1
                    existing["last_seen"] = _now()
                    merged = list(dict.fromkeys(list(existing.get("evidence_ids", [])) + list(evidence)))
                    existing["evidence_ids"] = merged[:32]
                    existing["value_score"] = max(float(existing.get("value_score", 0)), float(value_score))
                    existing["confidence"] = max(float(existing.get("confidence", 0)), float(confidence))
                    data["stats"]["reinforcements"] = int(data["stats"].get("reinforcements", 0)) + 1
                    self._save()
                    return {"status": "reinforced", "id": existing.get("id")}

            entry = {
                "id": self._entry_id(topic, question, answer),
                "topic": topic,
                "kind": kind,
                "question": question,
                "answer": answer,
                "evidence_ids": list(evidence),
                "value_score": round(float(value_score), 4),
                "confidence": round(float(confidence), 4),
                "support": 1,
                "first_seen": _now(),
                "last_seen": _now(),
            }
            data["entries"].append(entry)
            data["entries"] = data["entries"][-self.MAX_ENTRIES:]
            data["stats"]["promotions"] = int(data["stats"].get("promotions", 0)) + 1
            self._save()
            return {"status": "promoted", "id": entry["id"]}

    def update_frontier(self, topic: str, questions: Iterable) -> None:
        unresolved = []
        for q in questions:
            if bool(getattr(q, "resolved", False)):
                continue
            value = float(getattr(q, "value_score", 0.0) or 0.0)
            if value < 0.55:
                continue
            unresolved.append({
                "topic": topic,
                "qid": str(getattr(q, "qid", "")),
                "kind": str(getattr(q, "kind", "")),
                "question": str(getattr(q, "question", "")),
                "value_score": round(value, 4),
                "generation": int(getattr(q, "generation", 0) or 0),
                "last_seen": _now(),
            })
        unresolved.sort(key=lambda x: (-x["value_score"], x["question"]))
        with self._lock:
            data = self._load()
            # Replace this topic's frontier so solved questions disappear.
            data["frontier"] = [
                x for x in data["frontier"]
                if _jaccard(str(x.get("topic", "")), topic) < 0.75
            ]
            data["frontier"].extend(unresolved[:512])
            data["frontier"] = data["frontier"][-self.MAX_FRONTIER:]
            self._save()

    def frontier_for(self, topic: str, limit: int = 64) -> list[dict]:
        rows = []
        for row in self._load()["frontier"]:
            sim = _jaccard(topic, str(row.get("topic", "")))
            if sim >= 0.55:
                rows.append((sim, float(row.get("value_score", 0)), row))
        rows.sort(key=lambda x: (-x[0], -x[1]))
        return [dict(row) for _, _, row in rows[:limit]]

    def stats(self) -> dict:
        data = self._load()
        return {
            "entries": len(data["entries"]),
            "conflicts": len(data["conflicts"]),
            "frontier": len(data["frontier"]),
            **{k: int(v) for k, v in data.get("stats", {}).items()},
        }
