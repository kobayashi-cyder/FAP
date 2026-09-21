from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolIntent:
    name: str
    confidence: float = 0.95


class PersistentGoalState:
    """Small deterministic long-context store.

    This is not an LLM summary. It preserves explicit goals, constraints and
    user-declared facts so important state survives beyond the raw chat window.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(sid: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_.-]", "_", str(sid or "default"))[:80]
        return value or "default"

    def path(self, sid: str) -> Path:
        return self.root / f"{self._safe(sid)}.json"

    def load(self, sid: str) -> dict[str, Any]:
        p = self.path(sid)
        if not p.exists():
            return {"open_goal": "", "goals": [], "constraints": [], "facts": [], "updated_at": ""}
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return {
                    "open_goal": str(obj.get("open_goal", "")),
                    "goals": list(obj.get("goals", []))[-20:],
                    "constraints": list(obj.get("constraints", []))[-40:],
                    "facts": list(obj.get("facts", []))[-40:],
                    "updated_at": str(obj.get("updated_at", "")),
                }
        except Exception:
            pass
        return {"open_goal": "", "goals": [], "constraints": [], "facts": [], "updated_at": ""}

    @staticmethod
    def _append_unique(items: list[str], value: str, limit: int) -> list[str]:
        v = re.sub(r"\s+", " ", value).strip()
        if not v:
            return items[-limit:]
        out = [x for x in items if x != v]
        out.append(v)
        return out[-limit:]

    @staticmethod
    def _extract_goal(text: str) -> str:
        t = re.sub(r"\s+", " ", str(text or "")).strip()
        if not t:
            return ""
        if re.search(r"(目的|目標).{0,8}(は|:|：)", t):
            return t[:360]
        if re.search(r"(作って|作成して|構築して|実装して|直して|改善して|してください|してほしい|終わるまで|達成するまで)", t):
            return t[:360]
        return ""

    @staticmethod
    def _extract_constraints(text: str) -> list[str]:
        t = re.sub(r"\s+", " ", str(text or "")).strip()
        out: list[str] = []
        # Numeric / dimensional constraints.
        for m in re.finditer(r"\b\d+(?:\.\d+)?\s*(?:×\s*\d+(?:\.\d+)?)?\s*(?:ms|秒|分|時間|KB|MB|GB|個|件|回|文字|行|%|％|x|×)?", t, re.I):
            v = m.group(0).strip()
            if v and len(v) <= 40:
                out.append(v)
        # Explicit prohibitions and requirements.
        patterns = [
            r"[^。！？!?]{0,50}(?:しないで|使わない|禁止|不要|無し|なし)[^。！？!?]{0,30}",
            r"[^。！？!?]{0,50}(?:のみ|だけ|必須|固定|以内|以上|以下|未満)[^。！？!?]{0,30}",
            r"[^。！？!?]{0,40}(?:Qwen|Gemma|E2B|Pixel|Android|Python|HTML|JSON|Markdown)[^。！？!?]{0,40}",
        ]
        for pat in patterns:
            out.extend(x.strip() for x in re.findall(pat, t, re.I) if x.strip())
        # Keep full rule-like sentences when they express conditions.
        for sent in re.split(r"[。！？!?]+", t):
            s = sent.strip()
            if s and re.search(r"(たびに|なら|場合|条件|勝ち|負け|まで|以内|以上|以下|禁止|必須)", s):
                out.append(s[:180])
        dedup: list[str] = []
        for x in out:
            if x not in dedup:
                dedup.append(x)
        return dedup[:16]

    @staticmethod
    def _extract_facts(text: str) -> list[str]:
        t = re.sub(r"\s+", " ", str(text or "")).strip()
        out: list[str] = []
        for pat in [r"合言葉は[^。！？!?]{1,80}", r"(?:私は|この|それは|これは)[^。！？!?]{1,120}(?:です|だ|である)"]:
            out.extend(x.strip() for x in re.findall(pat, t) if x.strip())
        return out[:8]

    def update(self, sid: str, text: str) -> dict[str, Any]:
        state = self.load(sid)
        goal = self._extract_goal(text)
        if goal:
            state["open_goal"] = goal
            state["goals"] = self._append_unique(state["goals"], goal, 20)
        for c in self._extract_constraints(text):
            state["constraints"] = self._append_unique(state["constraints"], c, 40)
        for f in self._extract_facts(text):
            state["facts"] = self._append_unique(state["facts"], f, 40)
        state["updated_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        self.path(sid).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def summary(self, sid: str) -> str:
        s = self.load(sid)
        rows = []
        if s["open_goal"]:
            rows.append("現在の目標: " + s["open_goal"])
        if s["constraints"]:
            rows.append("保持中の条件: " + " / ".join(s["constraints"][-8:]))
        if s["facts"]:
            rows.append("保持中の明示情報: " + " / ".join(s["facts"][-6:]))
        return "\n".join(rows) if rows else "長期状態に明示的な目標・条件はまだありません。"


class MultiIntentPlanner:
    """Detect independent built-in tool intents in one user turn."""

    DETECTORS = (
        ("weather", re.compile(r"(天気|気温|降水|雨|雪|晴|曇|weather|temperature)", re.I)),
        ("datetime", re.compile(r"(何日|何時|曜日|日付|時刻|datetime|date|time)", re.I)),
        ("calculator", re.compile(r"(計算|いくら|何%|何％|\d\s*[+\-*/×÷^]\s*\d)", re.I)),
        ("memory", re.compile(r"(覚えて|記憶|前に言った|さっき|以前の会話|memory)", re.I)),
    )

    def detect(self, text: str) -> list[ToolIntent]:
        t = str(text or "")
        # Creation requests belong to Builder; do not fragment their requirements.
        if re.search(r"(作って|作成|生成|構築|build|create|make)", t, re.I):
            return []
        found: list[ToolIntent] = []
        for name, pat in self.DETECTORS:
            if pat.search(t):
                found.append(ToolIntent(name))
        return found if len(found) >= 2 else []


class DeliberationEngine:
    """Candidate-plan selection around the distilled circuits."""

    def __init__(self, distilled):
        self.distilled = distilled

    def plan(self, text: str, history: list[Mapping], state: Mapping[str, Any]) -> dict[str, Any]:
        context_rows = []
        for row in history[-12:]:
            role = row.get("role")
            value = str(row.get("text", "")).strip()
            if role in {"user", "assistant"} and value:
                context_rows.append(f"{role}:{value}")
        context = "\n".join(context_rows)
        acts = self.distilled.activate(text, context, limit=5)
        candidates: list[dict[str, Any]] = []
        for a in acts:
            spec = getattr(__import__("fap_v78_distilled"), "CIRCUITS")[a.name]
            score = float(a.score)
            if state.get("open_goal") and a.name == "planning":
                score += 1.5
            if state.get("constraints") and a.name == "constraint_aware":
                score += min(1.0, len(state.get("constraints", [])) * 0.08)
            candidates.append({
                "circuit": a.name,
                "score": round(score, 4),
                "plan": list(spec.get("plan", []))[:5],
            })
        candidates.sort(key=lambda x: (-x["score"], x["circuit"]))
        return {
            "candidates": candidates[:4],
            "selected": candidates[0]["circuit"] if candidates else "direct",
            "goal_present": bool(state.get("open_goal")),
            "constraint_count": len(state.get("constraints", [])),
        }


class CoverageCritic:
    """Cheap semantic coverage checks; never upgrades unknown facts into knowledge."""

    def evaluate(self, text: str, result: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
        reply = str(result.get("reply", ""))
        issues: list[str] = []
        if not reply.strip():
            issues.append("empty_reply")
        if re.search(r"(作って|作成|生成|構築)", text) and result.get("ok") and not result.get("artifacts"):
            # Some builder requests can legitimately ask only whether it is possible; only flag imperative creation.
            if re.search(r"(作って|作成して|生成して|構築して)", text):
                issues.append("artifact_missing")
        if state.get("constraints") and result.get("ok") and len(reply) < 12 and not result.get("artifacts"):
            issues.append("constraint_coverage_weak")
        unknown_marker = "確定回答できません" in reply or "分からない" in reply
        return {
            "verdict": "PARTIAL" if issues else "OK",
            "issues": issues,
            "unknown_boundary": unknown_marker,
        }
