from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import RepositoryKnowledgeIndex, RetrievalHit, sentences, terms


QUESTION_CUES = re.compile(r"[？?]|(なぜ|どうして|どう|何|教えて|説明|について|とは|できますか|できる)")
AUDIT_CUES = re.compile(r"(疑問|質問を出|問いを出|わからない点|分からない点|不明|未解決|限界|問題点|課題|全問|質問つぶし)")
CURRENT_CUES = re.compile(r"(最新|現在|リアルタイム|今日|明日|今週|今月|今年|現在地|何号|\d+号|いつ上陸|今どこ)", re.I)

MECHANISM_CUES = re.compile(r"(原因|ため|ので|によって|作用|力|仕組|機構|過程|駆動|発生|生じ|影響|決ま|関わ|reason|cause|mechanism)", re.I)
CONDITION_CUES = re.compile(r"(条件|場合|依存|変わ|スケール|場所|高度|時間|ほど|なら|では|depending|condition|scale)", re.I)
UNCERTAINTY_CUES = re.compile(r"(誤差|不確実|限界|近似|完全|未知|不足|必要|確率|幅|ばらつ|予測|観測|モデル|uncertain|error|limit|approx|probab)", re.I)
EVIDENCE_CUES = re.compile(r"(観測|測定|実験|データ|衛星|レーダー|モデル|検証|確認|予報|測る|observe|measure|data|experiment|model)", re.I)


@dataclass
class InquiryQuestion:
    qid: str
    kind: str
    question: str
    resolved: bool = False
    answer: str = ""
    evidence_ids: tuple[str, ...] = ()


def _clean_sentence(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if s and s[-1] not in "。.!?！？":
        s += "。"
    return s


class InquiryEngine:
    """Generic question generation + question resolution.

    The engine never branches on a topic name. It retrieves local knowledge,
    generates the same epistemic question types for any topic, tries to resolve
    each question from evidence, retries unresolved questions, and exposes what
    remains unknown.
    """

    def __init__(self, root: Path):
        self.index = RepositoryKnowledgeIndex(root)

    @staticmethod
    def _topic_label(hits: list[RetrievalHit], text: str) -> str:
        if hits:
            return hits[0].chunk.title
        compact = re.sub(r"\s+", " ", str(text or "")).strip(" ?？。")
        return compact[:48] or "この話題"

    @staticmethod
    def _generate_questions(topic: str) -> list[InquiryQuestion]:
        return [
            InquiryQuestion("known", "known", f"{topic}について、何が確実に分かっているか？"),
            InquiryQuestion("mechanism", "mechanism", f"{topic}は、どんな原因・仕組みで成り立つか？"),
            InquiryQuestion("conditions", "conditions", f"{topic}は、どの条件で答えや挙動が変わるか？"),
            InquiryQuestion("uncertainty", "uncertainty", f"{topic}について、何がまだ不確実・未確定か？"),
            InquiryQuestion("evidence", "evidence", f"{topic}をさらに確定するには、何を観測・確認すべきか？"),
        ]

    @staticmethod
    def _sentence_score(sentence: str, query: str, kind: str, hit_score: float) -> float:
        st = terms(sentence)
        qt = terms(query)
        lexical = len(st & qt) / max(1.0, math.sqrt(max(1, len(st))))
        cue = 0.0
        if kind == "mechanism" and MECHANISM_CUES.search(sentence):
            cue = 0.7
        elif kind == "conditions" and CONDITION_CUES.search(sentence):
            cue = 0.7
        elif kind == "uncertainty" and UNCERTAINTY_CUES.search(sentence):
            cue = 0.85
        elif kind == "evidence" and EVIDENCE_CUES.search(sentence):
            cue = 0.85
        elif kind == "known":
            cue = 0.35
        return lexical + cue + hit_score * 0.8

    def _answer_question(
        self,
        question: InquiryQuestion,
        query: str,
        hits: list[RetrievalHit],
    ) -> InquiryQuestion:
        ranked: list[tuple[float, str, str]] = []
        seen: set[str] = set()
        for hit in hits:
            for sentence in sentences(hit.chunk.text):
                key = re.sub(r"\W+", "", sentence)[:200]
                if not key or key in seen:
                    continue
                seen.add(key)
                score = self._sentence_score(sentence, query, question.kind, hit.score)
                ranked.append((score, sentence, hit.chunk.chunk_id))
        ranked.sort(key=lambda x: (-x[0], x[1]))

        threshold = {
            "known": 0.45,
            "mechanism": 0.72,
            "conditions": 0.75,
            "uncertainty": 0.84,
            "evidence": 0.84,
        }.get(question.kind, 0.75)

        chosen = [row for row in ranked[:3] if row[0] >= threshold]
        if not chosen:
            return question

        # One or two concise evidence sentences are enough to close a subquestion.
        answer = "".join(_clean_sentence(row[1]) for row in chosen[:2])
        ids = tuple(dict.fromkeys(row[2] for row in chosen[:2]))
        question.resolved = True
        question.answer = answer
        question.evidence_ids = ids
        return question

    def _resolve_round(
        self,
        text: str,
        context: str,
        questions: list[InquiryQuestion],
        base_hits: list[RetrievalHit],
    ) -> int:
        progress = 0
        for q in questions:
            if q.resolved:
                continue
            # Round-specific retrieval combines the user's topic with the
            # generated question. No topic-specific router is added here.
            hits = self.index.search(f"{text} {q.question}", context, 6)
            merged: dict[str, RetrievalHit] = {h.chunk.chunk_id: h for h in base_hits}
            for hit in hits:
                prior = merged.get(hit.chunk.chunk_id)
                if prior is None or hit.score > prior.score:
                    merged[hit.chunk.chunk_id] = hit
            qhits = sorted(merged.values(), key=lambda h: (-h.score, h.chunk.chunk_id))[:8]
            before = q.resolved
            self._answer_question(q, text, qhits)
            if q.resolved and not before:
                progress += 1
        return progress

    @staticmethod
    def _best_overview(text: str, hits: list[RetrievalHit]) -> str:
        ranked: list[tuple[float, str]] = []
        seen: set[str] = set()
        for hit in hits[:4]:
            for sentence in sentences(hit.chunk.text):
                key = re.sub(r"\W+", "", sentence)[:200]
                if not key or key in seen:
                    continue
                seen.add(key)
                overlap = len(terms(sentence) & terms(text))
                score = hit.score + min(0.9, overlap * 0.12)
                if MECHANISM_CUES.search(sentence):
                    score += 0.12
                ranked.append((score, sentence))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        chosen = [s for _, s in ranked[:4]]
        return "".join(_clean_sentence(x) for x in chosen)

    @staticmethod
    def _audit_reply(topic: str, questions: list[InquiryQuestion]) -> str:
        lines = [f"{topic}について、自己質問を出して潰します。"]
        for i, q in enumerate(questions, 1):
            if q.resolved:
                lines.append(f"{i}. Q: {q.question}\n   A: {q.answer}")
            else:
                lines.append(f"{i}. Q: {q.question}\n   A: 未解決。現在のローカル根拠だけでは確定できません。")
        resolved = sum(1 for q in questions if q.resolved)
        lines.append(f"解消: {resolved}/{len(questions)}。未解決は推測で埋めません。")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        t = str(text or "").strip()
        if len(t) < 2:
            return None

        context = self.index.context_from_history(history)
        hits = self.index.search(t, context, 8)
        if not hits or hits[0].score < 0.08:
            return None

        # Avoid hijacking casual statements that merely share a generic word.
        if not QUESTION_CUES.search(t) and len(t) < 12:
            return None

        topic = self._topic_label(hits, t)
        questions = self._generate_questions(topic)

        # First pass from the retrieved evidence, then one focused retry for
        # unresolved questions. Stop when no new question can be closed.
        for q in questions:
            self._answer_question(q, t, hits)
        rounds = 1
        if any(not q.resolved for q in questions):
            progress = self._resolve_round(t, context, questions, hits)
            rounds = 2
            if progress == 0:
                rounds = 1

        audit_mode = bool(AUDIT_CUES.search(t))
        current_request = bool(CURRENT_CUES.search(t))
        resolved = sum(1 for q in questions if q.resolved)
        unresolved = len(questions) - resolved

        evidence = []
        for hit in hits[:5]:
            evidence.append({
                "id": hit.chunk.chunk_id,
                "title": hit.chunk.title,
                "source": hit.chunk.source,
                "score": hit.score,
            })

        # A current/live request cannot be satisfied from a static local corpus,
        # even when the underlying mechanism is understood.
        needs_live_data = bool(current_request and any(
            re.search(r"(最新|観測|予報|現在|リアルタイム|データが必要)", h.chunk.text)
            for h in hits[:5]
        ))

        if audit_mode:
            reply = self._audit_reply(topic, questions)
        else:
            reply = self._best_overview(t, hits)
            if not reply:
                return None
            if unresolved:
                reply += f" なお、内部の自己質問は{resolved}/{len(questions)}件まで根拠付きで解消でき、残り{unresolved}件は未解決として保持しています。"
            if needs_live_data:
                reply += " この問いの現在値・最新予測を確定するには、静的知識だけでなく最新データが必要です。"

        return {
            "ok": True,
            "reply": reply,
            "confidence": round(min(0.97, 0.68 + hits[0].score * 0.24), 3),
            "needs_teacher": False,
            "local": True,
            "inquiry_reasoning": True,
            "question_generation": True,
            "question_resolution": True,
            "topic": topic,
            "inquiry_rounds": rounds,
            "generated_questions": len(questions),
            "resolved_questions": resolved,
            "unresolved_questions": unresolved,
            "audit_mode": audit_mode,
            "needs_live_data": needs_live_data,
            "questions": [
                {
                    "id": q.qid,
                    "kind": q.kind,
                    "question": q.question,
                    "resolved": q.resolved,
                    "answer": q.answer,
                    "evidence_ids": list(q.evidence_ids),
                }
                for q in questions
            ],
            "evidence": evidence,
        }
