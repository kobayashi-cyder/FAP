from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Mapping


_JA = re.compile(r"[一-龥ぁ-んァ-ンー]+")
_LATIN = re.compile(r"[A-Za-z0-9_+.-]+")


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _clean(text: str, limit: int = 360) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip(" \t\r\n。")
    return s[:limit]


def _features(text: str) -> set[str]:
    """Cheap language-agnostic-ish semantic features.

    Japanese has no spaces, so use character bigrams plus Latin/number tokens.
    This is intentionally deterministic and dependency-free.
    """
    s = _clean(text, 1200).lower()
    out = {x.lower() for x in _LATIN.findall(s)}
    for chunk in _JA.findall(s):
        if len(chunk) <= 2:
            out.add(chunk)
        else:
            out.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return out


def _similarity(a: str, b: str) -> float:
    x, y = _features(a), _features(b)
    if not x or not y:
        return 0.0
    return len(x & y) / max(1, len(x | y))


class SemanticMemoryStore:
    """Compact long-term semantic state independent of raw chat length.

    It stores only explicit goals, constraints, preferences, selected facts and
    verified task experiences. Similar items are merged, named slots are
    superseded by newer user statements, and low-salience items are compacted.
    No embedding model or external service is required.
    """

    MAX_ENTRIES = 128

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _safe(sid: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_.-]", "_", str(sid or "default"))[:80]
        return value or "default"

    def path(self, sid: str) -> Path:
        return self.root / f"{self._safe(sid)}.json"

    @staticmethod
    def _blank() -> dict[str, Any]:
        return {"version": 1, "entries": [], "updated_at": ""}

    def load(self, sid: str) -> dict[str, Any]:
        key = self._safe(sid)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        p = self.path(sid)
        if not p.exists():
            obj = self._blank()
            self._cache[key] = obj
            return obj
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and isinstance(obj.get("entries"), list):
                obj.setdefault("version", 1)
                obj.setdefault("updated_at", "")
                self._cache[key] = obj
                return obj
        except Exception:
            pass
        obj = self._blank()
        self._cache[key] = obj
        return obj

    @staticmethod
    def _slot(category: str, text: str) -> str:
        t = text.lower()
        if category == "preference":
            if re.search(r"(出力|回答).{0,12}(言語|日本語|英語)|(?:日本語|英語).{0,12}(出力|回答)", text, re.I):
                return "preference:output_language"
            if re.search(r"(出力|回答).{0,12}(形式|フォーマット)|(?:json|markdown|html|csv).{0,12}(形式|出力)", text, re.I):
                return "preference:output_format"
            if re.search(r"(簡潔|詳細|短く|長く|箇条書き|表形式)", text):
                return "preference:response_style"
        if category == "goal" and re.search(r"(目的|目標).{0,10}(は|:|：)", text):
            return "goal:primary"
        if category == "constraint":
            if "qwen" in t:
                return "constraint:model:qwen"
            if re.search(r"gemma|e2b", t):
                return "constraint:model:teacher"
            if re.search(r"ram|メモリ", t):
                return "constraint:memory"
        if category == "fact":
            if re.search(r"合言葉", text):
                return "fact:passphrase"
            if re.search(r"(?:名前|名称).{0,8}(は|:|：)", text):
                return "fact:name"
        return ""

    @staticmethod
    def _classify_sentence(sentence: str, explicit_remember: bool = False) -> str | None:
        s = _clean(sentence)
        if not s or len(s) < 3:
            return None
        if re.search(r"[?？]$", sentence):
            return None
        if re.search(r"(目的|目標).{0,12}(は|:|：)|(?:完成|達成|実装).{0,20}(目的|目標)", s):
            return "goal"
        if re.search(r"(使わない|禁止|不要|無し|なし|必須|固定|以内|以上|以下|未満|だけ|のみ|制約|条件|RAM|メモリ|Qwen|Gemma|E2B)", s, re.I):
            return "constraint"
        if re.search(r"(標準|デフォルト|優先|好み|毎回|基本|出力|回答|形式|言語).{0,40}(にする|でお願い|を使う|優先|固定|形式|日本語|英語|json|markdown|html|csv)", s, re.I):
            return "preference"
        if re.search(r"(日本語|英語).{0,20}(使う|回答|出力|標準)", s, re.I):
            return "preference"
        if explicit_remember:
            return "fact"
        if re.search(r"(合言葉|名前|名称|バージョン|端末|環境).{0,16}(は|:|：|=)", s, re.I):
            return "fact"
        return None

    @staticmethod
    def _sentences(text: str) -> list[str]:
        # Preserve punctuation only as separators; short newline clauses count too.
        rows = []
        for chunk in re.split(r"[。！？!?\n]+", str(text or "")):
            c = _clean(chunk)
            if c:
                rows.append(c)
        return rows[:24]

    def _upsert(self, state: dict[str, Any], category: str, text: str, source: str = "user", verified: bool = True) -> None:
        entries = state.setdefault("entries", [])
        text = _clean(text)
        if not text:
            return
        slot = self._slot(category, text)
        now = _now()

        # Named slots are current-state memories. A newer explicit value supersedes the old one.
        if slot:
            for e in entries:
                if e.get("slot") == slot and not e.get("superseded"):
                    if e.get("text") != text:
                        prev = list(e.get("previous", []))[-2:]
                        prev.append(str(e.get("text", "")))
                        e["previous"] = prev[-3:]
                        e["text"] = text
                    e["mentions"] = int(e.get("mentions", 1)) + 1
                    e["salience"] = min(1.0, float(e.get("salience", 0.7)) + 0.08)
                    e["last_seen"] = now
                    e["verified"] = bool(verified)
                    return

        # Merge close paraphrases inside the same category.
        best = None
        best_score = 0.0
        for e in entries:
            if e.get("superseded") or e.get("category") != category or e.get("slot"):
                continue
            score = _similarity(text, str(e.get("text", "")))
            if score > best_score:
                best, best_score = e, score
        if best is not None and best_score >= 0.58:
            if len(text) > len(str(best.get("text", ""))):
                best["text"] = text
            best["mentions"] = int(best.get("mentions", 1)) + 1
            best["salience"] = min(1.0, float(best.get("salience", 0.65)) + 0.06)
            best["last_seen"] = now
            best["verified"] = bool(best.get("verified", False) or verified)
            return

        base_salience = {"goal": 0.92, "constraint": 0.90, "preference": 0.82, "fact": 0.75, "experience": 0.58}.get(category, 0.55)
        entries.append({
            "category": category,
            "slot": slot,
            "text": text,
            "source": source,
            "verified": bool(verified),
            "mentions": 1,
            "salience": base_salience,
            "first_seen": now,
            "last_seen": now,
            "previous": [],
        })

    def _compact(self, state: dict[str, Any]) -> None:
        entries = [e for e in state.get("entries", []) if not e.get("superseded")]
        if len(entries) <= self.MAX_ENTRIES:
            state["entries"] = entries
            return
        # Protect current goals/constraints/slots, then keep high-salience repeated items.
        def rank(e: Mapping[str, Any]) -> tuple[float, int, str]:
            protected = 1.0 if e.get("category") in {"goal", "constraint"} or e.get("slot") else 0.0
            score = protected * 2.0 + float(e.get("salience", 0.0)) + min(0.8, int(e.get("mentions", 1)) * 0.04)
            return (score, int(e.get("mentions", 1)), str(e.get("last_seen", "")))
        entries.sort(key=rank, reverse=True)
        state["entries"] = entries[: self.MAX_ENTRIES]

    def absorb_user(self, sid: str, text: str) -> dict[str, Any]:
        raw = str(text or "")
        recall_question = bool(
            re.search(
                r"(?:覚えて(?:いる|る)|記憶して(?:いる|る)).{0,8}[?？]|"
                r"(?:覚えて(?:いる|る)|記憶して(?:いる|る)).{0,8}(?:か|かな)$",
                raw,
            )
        )
        explicit = bool(
            re.search(r"(覚えて|記憶して|今後.*覚え)", raw)
        ) and not recall_question
        classified = []
        for sentence in self._sentences(text):
            category = self._classify_sentence(sentence, explicit_remember=explicit)
            if category:
                cleaned = re.sub(r"^(?:これを|このことを)?(?:覚えて|記憶して)[、,:：\s]*", "", sentence).strip()
                classified.append((category, cleaned or sentence))

        # Most conversation turns carry no durable memory. Avoid both mutation
        # and disk writes in that overwhelmingly common case.
        state = self.load(sid)
        if not classified:
            return state

        for category, value in classified:
            self._upsert(state, category, value, "user", True)
        self._compact(state)
        state["updated_at"] = _now()
        self._cache[self._safe(sid)] = state
        self.path(sid).write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return state

    def absorb_outcome(self, sid: str, text: str, ability: str, verdict: str, artifacts: list[Mapping[str, Any]] | None = None) -> None:
        if verdict != "OK":
            return
        # Only retain meaningful successful task experiences, not every chat answer.
        if ability not in {"builder", "multi"} and not artifacts:
            return
        state = self.load(sid)
        family = task_family(text)
        artifact_names = []
        for a in artifacts or []:
            name = a.get("name") or a.get("filename") or a.get("path")
            if name:
                artifact_names.append(str(name).split("/")[-1])
        tail = f" / artifacts={','.join(artifact_names[:3])}" if artifact_names else ""
        self._upsert(state, "experience", f"{family}: {ability} succeeded{tail}", "runtime", True)
        self._compact(state)
        state["updated_at"] = _now()
        self._cache[self._safe(sid)] = state
        self.path(sid).write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def retrieve(self, sid: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        state = self.load(sid)
        q = _clean(query)
        qf = _features(q)
        generic = bool(re.search(r"(覚えている|重要情報|長期記憶|記憶一覧|保持している|これまでの設定)", q))
        cat_boost = set()
        if re.search(r"目的|目標", q):
            cat_boost.add("goal")
        if re.search(r"条件|制約|禁止|必須", q):
            cat_boost.add("constraint")
        if re.search(r"好み|標準|デフォルト|出力|回答|言語|形式", q):
            cat_boost.add("preference")
        if re.search(r"合言葉|名前|事実", q):
            cat_boost.add("fact")

        ranked = []
        for e in state.get("entries", []):
            ef = _features(str(e.get("text", "")))
            overlap = len(qf & ef) / max(1, len(qf | ef)) if qf and ef else 0.0
            score = overlap * 3.0 + float(e.get("salience", 0.0)) * 0.55
            if e.get("category") in cat_boost:
                score += 1.15
            if e.get("slot") and any(k in q.lower() for k in ["出力", "回答", "言語", "形式", "標準"]):
                score += 0.4
            if generic:
                score += 0.6
            if int(e.get("mentions", 1)) > 1:
                score += min(0.35, int(e.get("mentions", 1)) * 0.03)
            if score >= (0.35 if generic or cat_boost else 0.75):
                ranked.append((score, e))
        ranked.sort(key=lambda x: (-x[0], -float(x[1].get("salience", 0.0)), str(x[1].get("text", ""))))
        return [dict(e) for _, e in ranked[: max(1, int(limit))]]

    def render(self, sid: str, query: str, limit: int = 8) -> str:
        rows = self.retrieve(sid, query, limit)
        if not rows:
            return "長期意味記憶に、この質問へ対応する明示情報はありません。"
        labels = {"goal": "目標", "constraint": "条件", "preference": "設定", "fact": "情報", "experience": "経験"}
        return "長期意味記憶:\n" + "\n".join(f"- {labels.get(r.get('category'), r.get('category'))}: {r.get('text')}" for r in rows)

    def stats(self, sid: str) -> dict[str, Any]:
        state = self.load(sid)
        counts: dict[str, int] = {}
        for e in state.get("entries", []):
            cat = str(e.get("category", "other"))
            counts[cat] = counts.get(cat, 0) + 1
        return {"entries": len(state.get("entries", [])), "max_entries": self.MAX_ENTRIES, "categories": counts, "updated_at": state.get("updated_at", "")}


def task_family(text: str) -> str:
    t = str(text or "")
    if re.search(r"python|\.py\b|コード|スクリプト|javascript|\bjs\b|html|json|markdown", t, re.I):
        return "code"
    if re.search(r"ゲーム|game|盤面|テトリス|マインスイーパー|2048|pong|snake", t, re.I):
        return "game"
    if re.search(r"天気|気温|降水|weather", t, re.I):
        return "weather"
    if re.search(r"何日|何時|曜日|日付|時刻|datetime", t, re.I):
        return "datetime"
    if re.search(r"計算|\d\s*[+\-*/×÷]\s*\d", t):
        return "calculator"
    if re.search(r"画像|写真|イラスト|image|photo", t, re.I):
        return "image"
    if re.search(r"覚えて|記憶|前に|さっき|memory", t, re.I):
        return "memory"
    if re.search(r"エラー|例外|不具合|デバッグ|動かない", t):
        return "debug"
    if re.search(r"続き|それ|これ|その|前の", t):
        return "followup"
    return "general"


class AdaptiveRoutingLedger:
    """Bounded outcome-based routing priors.

    Learning can only influence ambiguous/implicit requests. Explicit strong
    intents remain locked to deterministic routing. This prevents a few bad
    outcomes from teaching the router to ignore clear user instructions.
    """

    MAX_FAMILIES = 32

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {"version": 1, "families": {}, "updated_at": ""}
            return self._cache
        try:
            obj = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and isinstance(obj.get("families"), dict):
                self._cache = obj
                return obj
        except Exception:
            pass
        self._cache = {"version": 1, "families": {}, "updated_at": ""}
        return self._cache

    def record(self, text: str, ability: str, verdict: str) -> dict[str, Any]:
        family = task_family(text)
        state = self.load()
        fam = state.setdefault("families", {}).setdefault(family, {})
        rec = fam.setdefault(str(ability), {"ok": 0, "partial": 0, "ng": 0, "last": ""})
        key = "ok" if verdict == "OK" else ("partial" if verdict == "PARTIAL" else "ng")
        rec[key] = int(rec.get(key, 0)) + 1
        rec["last"] = _now()
        state["updated_at"] = _now()
        # Families are fixed and tiny, but keep an explicit bound.
        if len(state["families"]) > self.MAX_FAMILIES:
            keep = sorted(state["families"].items(), key=lambda kv: max((x.get("last", "") for x in kv[1].values()), default=""), reverse=True)[: self.MAX_FAMILIES]
            state["families"] = dict(keep)
        self._cache = state
        self.path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return state

    @staticmethod
    def _strong_explicit(text: str) -> bool:
        t = str(text or "")
        return bool(re.search(
            r"(作って|作成|生成|構築|build|create|make|天気|気温|降水|何日|何時|曜日|日付|時刻|計算|画像.{0,8}(生成|作って|描いて)|覚えて|記憶)",
            t, re.I,
        ))

    def suggest(self, text: str, intent) -> dict[str, Any]:
        family = task_family(text)
        state = self.load()
        stats = state.get("families", {}).get(family, {})
        out = {
            "family": family,
            "base": getattr(intent, "name", "chat"),
            "selected": getattr(intent, "name", "chat"),
            "applied": False,
            "reason": "no learned override",
            "evidence": {},
        }
        if self._strong_explicit(text):
            out["reason"] = "explicit intent locked"
            return out

        scored = []
        for ability, rec in stats.items():
            ok = int(rec.get("ok", 0)); partial = int(rec.get("partial", 0)); ng = int(rec.get("ng", 0))
            n = ok + partial + ng
            # Beta-style smoothing; partial gets half credit.
            rate = (ok + 0.5 * partial + 1.0) / (n + 2.0)
            if n >= 2:
                scored.append((rate, n, ability))
            out["evidence"][ability] = {"n": n, "success_rate": round(rate, 3)}
        if not scored:
            return out
        scored.sort(reverse=True)
        rate, n, ability = scored[0]
        base_name = getattr(intent, "name", "chat")

        # Conservative learned inference: repeated successful code/build routes may
        # resolve implicit request wording such as "Pythonコードお願い".
        if family == "code" and base_name == "chat" and ability == "builder" and n >= 2 and rate >= 0.72:
            if re.search(r"(お願い|ほしい|欲しい|頼む|ください|やって)", str(text or "")):
                out.update({"selected": "builder", "applied": True, "reason": "learned code-request prior"})
                return out

        # For genuinely close base candidates, allow only a small learned nudge.
        candidates = dict(getattr(intent, "candidates", []) or [])
        base_score = float(candidates.get(base_name, 0.0))
        candidate_score = float(candidates.get(ability, 0.0))
        if ability != base_name and n >= 3 and rate >= 0.80 and base_score - candidate_score <= 0.12:
            out.update({"selected": ability, "applied": True, "reason": "learned prior on ambiguous candidates"})
        return out

    def stats(self) -> dict[str, Any]:
        return self.load()
