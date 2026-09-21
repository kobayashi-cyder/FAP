from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fap_knowledge_retrieval import RepositoryKnowledgeIndex, RetrievalHit, sentences, terms
from fap_epistemic_learning import EpistemicLedger, QuestionValueScorer


QUESTION_CUES = re.compile(r"[？?]|(なぜ|どうして|どう|何|教えて|説明|について|とは|できますか|できる)")
AUDIT_CUES = re.compile(r"(疑問|質問を出|問いを出|問い出し|問い潰し|質問つぶし|わからない点|分からない点|不明|未解決|限界|問題点|課題|全問)")
CURRENT_CUES = re.compile(r"(最新|現在|リアルタイム|今日|明日|今週|今月|今年|現在地|何号|\d+号|いつ上陸|今どこ)", re.I)
COUNT_CUES = re.compile(r"(\d{1,3})\s*(?:問|件)")

CUES = {
    "known": re.compile(r"(である|です|は、|とは|known|is )", re.I),
    "definition": re.compile(r"(とは|定義|意味|である|is |means|defined)", re.I),
    "components": re.compile(r"(組み合わせ|要素|成分|部分|構成|含|components?|consists?|include)", re.I),
    "mechanism": re.compile(r"(原因|ため|ので|によって|作用|力|仕組|機構|過程|駆動|発生|生じ|影響|決ま|関わ|reason|cause|mechanism)", re.I),
    "cause": re.compile(r"(原因|によって|ため|駆動|発生|生じ|cause|because|driv)", re.I),
    "effect": re.compile(r"(影響|結果|変わ|増|減|曲|加速|抑|effects?|result|increase|decrease)", re.I),
    "dependency": re.compile(r"(依存|関係|組み合わせ|影響|depends?|relation|coupl)", re.I),
    "conditions": re.compile(r"(条件|場合|依存|変わ|なら|では|when|condition|depend)", re.I),
    "spatial": re.compile(r"(場所|高度|空間|距離|緯度|地表|水平|鉛直|spatial|height|latitude|distance)", re.I),
    "temporal": re.compile(r"(時間|先|長く|短く|将来|予報時間|time|future|horizon)", re.I),
    "scale": re.compile(r"(スケール|大規模|小さい|広い|局地|scale|large|small)", re.I),
    "interaction": re.compile(r"(同時|組み合わせ|釣り合|相互|影響|interaction|balance|coupl)", re.I),
    "dominance": re.compile(r"(支配|重要|主に|強く|基本|dominant|main|important)", re.I),
    "sensitivity": re.compile(r"(変わ|強く|弱く|増幅|誤差|sensitive|change|amplif)", re.I),
    "assumption": re.compile(r"(近似|モデル|仮定|理想|条件|assum|approx|model)", re.I),
    "boundary": re.compile(r"(限界|別|必要|できない|完全|boundary|limit|cannot|need)", re.I),
    "exception": re.compile(r"(場合|ただし|一方|異な|わけでは|例外|however|except|not always)", re.I),
    "failure": re.compile(r"(誤差|失敗|不足|できない|完全|増幅|error|fail|insufficient)", re.I),
    "uncertainty": re.compile(r"(誤差|不確実|限界|近似|完全|未知|不足|確率|幅|ばらつ|uncertain|error|limit|approx|probab)", re.I),
    "error": re.compile(r"(誤差|近似|増幅|ばらつ|error|approx|uncertain)", re.I),
    "observability": re.compile(r"(観測|測定|衛星|レーダー|地上|航空|observe|measure|satellite|radar)", re.I),
    "evidence": re.compile(r"(観測|測定|実験|データ|衛星|レーダー|モデル|検証|確認|測る|observe|measure|data|experiment|model)", re.I),
    "validation": re.compile(r"(検証|確認|比較|観測|データ|validation|verify|test|compare)", re.I),
    "prediction": re.compile(r"(予測|予報|将来|進路|forecast|predict|future)", re.I),
    "counterfactual": re.compile(r"(変わ|なら|場合|影響|if |without|change)", re.I),
    "alternative": re.compile(r"(一方|異な|複数|別|alternative|different|multiple)", re.I),
    "falsify": re.compile(r"(検証|確認|観測|測定|反例|test|verify|observe|measure)", re.I),
    "control": re.compile(r"(制御|操作|変え|調整|control|intervention|change)", re.I),
    "invariant": re.compile(r"(保存|一定|変わら|constant|conserv|invariant)", re.I),
    "reversibility": re.compile(r"(可逆|不可逆|戻|revers|irrevers)", re.I),
    "decomposition": re.compile(r"(要素|部分|組み合わせ|複数|段階|component|part|stage)", re.I),
    "transfer": re.compile(r"(場合|場所|スケール|異な|適用|apply|transfer|different)", re.I),
    "live_data": re.compile(r"(最新|現在|観測|予報|リアルタイム|データが必要|current|latest|real.time)", re.I),
    "role": re.compile(r"(役割|影響|重要|関わ|作用|role|effect|important)", re.I),
}

BASE_SPECS: tuple[tuple[str, str], ...] = (
    ("known", "{topic}について、何が確実に分かっているか？"),
    ("definition", "{topic}を一文で定義すると何か？"),
    ("definition", "{topic}の中心概念は何か？"),
    ("components", "{topic}を構成する主要な要素は何か？"),
    ("decomposition", "{topic}をどの部分問題に分解できるか？"),
    ("mechanism", "{topic}はどんな仕組みで成り立つか？"),
    ("cause", "{topic}を生じさせる主な原因は何か？"),
    ("effect", "{topic}が生む主な結果・影響は何か？"),
    ("dependency", "{topic}は何に依存するか？"),
    ("conditions", "{topic}はどの条件で変わるか？"),
    ("conditions", "{topic}が成立しやすい条件は何か？"),
    ("conditions", "{topic}が成立しにくい条件は何か？"),
    ("spatial", "{topic}には場所・空間による違いがあるか？"),
    ("temporal", "{topic}には時間による違いがあるか？"),
    ("scale", "{topic}はスケールが変わるとどう変わるか？"),
    ("interaction", "{topic}では複数の要因がどう相互作用するか？"),
    ("dominance", "{topic}で支配的な要因は何か？"),
    ("sensitivity", "{topic}はどの要因の変化に敏感か？"),
    ("assumption", "{topic}の説明にはどんな仮定・近似があるか？"),
    ("boundary", "{topic}の説明・モデルの適用限界は何か？"),
    ("exception", "{topic}の一般則がそのまま当てはまらない場合はあるか？"),
    ("failure", "{topic}の予測や説明が失敗する主な理由は何か？"),
    ("uncertainty", "{topic}について何がまだ不確実か？"),
    ("error", "{topic}で誤差はどこから入るか？"),
    ("observability", "{topic}のどの量を直接観測・測定できるか？"),
    ("evidence", "{topic}を確かめる根拠・データは何か？"),
    ("validation", "{topic}の説明をどう検証できるか？"),
    ("prediction", "{topic}から何を予測できるか？"),
    ("prediction", "{topic}の予測可能性はどこまでか？"),
    ("counterfactual", "{topic}の主要因が無かったら何が変わるか？"),
    ("alternative", "{topic}を説明する別の見方・要因はあるか？"),
    ("falsify", "{topic}の説明を反証するには何を観測すべきか？"),
    ("control", "{topic}に介入・制御できる量はあるか？"),
    ("invariant", "{topic}で保たれる量・関係はあるか？"),
    ("reversibility", "{topic}は可逆的か、それとも不可逆性が重要か？"),
    ("transfer", "{topic}の説明は別の条件・場所にも適用できるか？"),
    ("live_data", "{topic}を今この瞬間について答えるには何の最新データが要るか？"),
    ("known", "{topic}について既知の事実と推論を分けるとどうなるか？"),
    ("uncertainty", "{topic}について『分かったつもり』になりやすい点は何か？"),
    ("evidence", "{topic}で追加情報を一つ得られるなら何を優先すべきか？"),
)

RELATED_SPECS: tuple[tuple[str, str], ...] = (
    ("role", "{subject}は{topic}の中でどんな役割を持つか？"),
    ("interaction", "{subject}は{topic}の他の要因とどう相互作用するか？"),
    ("conditions", "{subject}の影響はどの条件で強く・弱くなるか？"),
    ("sensitivity", "{subject}が変化すると{topic}の結果はどう変わるか？"),
    ("evidence", "{subject}の影響を確認するには何を観測・測定すべきか？"),
)


@dataclass
class InquiryQuestion:
    qid: str
    kind: str
    question: str
    generation: int = 0
    parent_id: str = ""
    resolved: bool = False
    answer: str = ""
    evidence_ids: tuple[str, ...] = ()
    value_score: float = 0.0
    attempts: int = 0
    recalled: bool = False


def _clean_sentence(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if s and s[-1] not in "。.!?！？":
        s += "。"
    return s


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ.get(name, str(default)))))
    except Exception:
        return default


class InquiryEngine:
    """Mass generic question generation + evidence-grounded resolution.

    No topic-specific routing lives here. Topic growth is data-driven through
    knowledge/*.jsonl. The engine generates many epistemic questions, resolves
    them against retrieved evidence, expands from resolved answers into related
    concepts, retries unresolved questions, and preserves unknowns explicitly.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.index = RepositoryKnowledgeIndex(root)
        self.scorer = QuestionValueScorer()
        self.ledger = EpistemicLedger(root)
        self.default_target = _env_int("FAP_INQUIRY_TARGET", 256, 32, 2048)
        self.max_rounds = _env_int("FAP_INQUIRY_ROUNDS", 8, 1, 16)
        self.resolve_budget = _env_int("FAP_INQUIRY_RESOLVE_BUDGET", 512, 64, 2048)
        self.display_limit = _env_int("FAP_INQUIRY_DISPLAY", 32, 8, 96)

    @staticmethod
    def _topic_label(hits: list[RetrievalHit], text: str) -> str:
        if hits:
            return hits[0].chunk.title
        compact = re.sub(r"\s+", " ", str(text or "")).strip(" ?？。")
        return compact[:48] or "この話題"

    def _target_from_text(self, text: str) -> int:
        m = COUNT_CUES.search(str(text or ""))
        if m:
            return max(16, min(2048, int(m.group(1))))
        if re.search(r"(とにかく増|大量|できるだけ多|最大限|徹底的|限界まで|可能な限り)", str(text or "")):
            return 2048
        return self.default_target

    @staticmethod
    def _generate_questions(topic: str, target: int) -> list[InquiryQuestion]:
        out: list[InquiryQuestion] = []
        for i, (kind, template) in enumerate(BASE_SPECS):
            out.append(InquiryQuestion(
                qid=f"g0-{i:03d}",
                kind=kind,
                question=template.format(topic=topic),
                generation=0,
            ))
            if len(out) >= target:
                break
        return out

    @staticmethod
    def _cue_score(kind: str, sentence: str) -> float:
        pat = CUES.get(kind)
        return 0.78 if pat and pat.search(sentence) else 0.0

    @classmethod
    def _sentence_score(cls, sentence: str, query: str, kind: str, hit_score: float) -> float:
        st = terms(sentence)
        qt = terms(query)
        lexical = len(st & qt) / max(1.0, math.sqrt(max(1, len(st))))
        return lexical + cls._cue_score(kind, sentence) + hit_score * 0.85

    @staticmethod
    def _threshold(kind: str) -> float:
        if kind in {"known", "definition"}:
            return 0.48
        if kind in {"uncertainty", "error", "boundary", "failure", "live_data"}:
            return 0.88
        if kind in {"evidence", "observability", "validation", "falsify"}:
            return 0.82
        return 0.74

    def _answer_question(
        self,
        question: InquiryQuestion,
        query: str,
        hits: list[RetrievalHit],
    ) -> InquiryQuestion:
        question.attempts += 1

        # Persistent recall is allowed only for previously promoted conclusions
        # that still retain their original evidence IDs.
        recalled = self.ledger.recall(question.question)
        if recalled and recalled.get("evidence_ids"):
            question.resolved = True
            question.answer = str(recalled.get("answer", ""))
            question.evidence_ids = tuple(str(x) for x in recalled.get("evidence_ids", []))
            question.recalled = True
            return question

        ranked: list[tuple[float, str, str]] = []
        seen: set[str] = set()
        for hit in hits:
            for sentence in sentences(hit.chunk.text):
                key = re.sub(r"\W+", "", sentence)[:240]
                if not key or key in seen:
                    continue
                seen.add(key)
                score = self._sentence_score(sentence, query, question.kind, hit.score)
                ranked.append((score, sentence, hit.chunk.chunk_id))
        ranked.sort(key=lambda x: (-x[0], x[1]))

        chosen = [row for row in ranked[:4] if row[0] >= self._threshold(question.kind)]
        if not chosen:
            return question

        question.resolved = True
        question.answer = "".join(_clean_sentence(row[1]) for row in chosen[:2])
        question.evidence_ids = tuple(dict.fromkeys(row[2] for row in chosen[:2]))
        return question

    def _focused_hits(
        self,
        text: str,
        question: InquiryQuestion,
        context: str,
        base_hits: list[RetrievalHit],
    ) -> list[RetrievalHit]:
        hits = self.index.search(f"{text} {question.question}", context, 10)
        merged: dict[str, RetrievalHit] = {h.chunk.chunk_id: h for h in base_hits}
        for hit in hits:
            prior = merged.get(hit.chunk.chunk_id)
            if prior is None or hit.score > prior.score:
                merged[hit.chunk.chunk_id] = hit
        return sorted(merged.values(), key=lambda h: (-h.score, h.chunk.chunk_id))[:12]

    def _resolve_round(
        self,
        text: str,
        context: str,
        questions: list[InquiryQuestion],
        base_hits: list[RetrievalHit],
    ) -> int:
        progress = 0
        unresolved = [q for q in questions if not q.resolved]
        unresolved.sort(key=lambda q: (-q.value_score, q.attempts, q.generation, q.qid))
        for q in unresolved[:self.resolve_budget]:
            before = q.resolved
            self._answer_question(q, text, self._focused_hits(text, q, context, base_hits))
            if q.resolved and not before:
                progress += 1
        return progress

    def _expand_from_answers(
        self,
        topic: str,
        text: str,
        context: str,
        questions: list[InquiryQuestion],
        target: int,
    ) -> int:
        if len(questions) >= target:
            return 0

        known_subjects = {topic}
        for q in questions:
            if q.parent_id:
                known_subjects.add(q.parent_id)

        candidate_hits: dict[str, RetrievalHit] = {}
        resolved = [q for q in questions if q.resolved and q.answer]
        # Use resolved answers to discover related local concepts. This is the
        # "answer -> next questions" loop rather than a fixed topic tree.
        for q in resolved[-24:]:
            for hit in self.index.search(q.answer, context, 5):
                prior = candidate_hits.get(hit.chunk.chunk_id)
                if prior is None or hit.score > prior.score:
                    candidate_hits[hit.chunk.chunk_id] = hit

        added = 0
        serial = len(questions)
        for hit in sorted(candidate_hits.values(), key=lambda h: (-h.score, h.chunk.chunk_id)):
            subject = hit.chunk.title
            if subject in known_subjects:
                continue
            known_subjects.add(subject)
            for kind, template in RELATED_SPECS:
                if len(questions) >= target:
                    return added
                qid = f"g1-{serial:03d}"
                serial += 1
                questions.append(InquiryQuestion(
                    qid=qid,
                    kind=kind,
                    question=template.format(subject=subject, topic=topic),
                    generation=1,
                    parent_id=subject,
                ))
                added += 1
        return added

    def _fill_generic(self, topic: str, questions: list[InquiryQuestion], target: int) -> int:
        """Fill to target by combining dimensions without adding topic rules."""
        if len(questions) >= target:
            return 0
        serial = len(questions)
        added = 0
        cycles = (
            ("mechanism", "別の角度から、{topic}の因果連鎖を一段ずつ分けるとどうなるか？"),
            ("conditions", "{topic}で前提条件を一つ変えると、どの結論が最初に変わるか？"),
            ("uncertainty", "{topic}で最も答えが不安定になりやすい部分はどこか？"),
            ("evidence", "{topic}の未解決点を一つ減らすための最小追加データは何か？"),
            ("alternative", "{topic}について同じ観測を説明し得る別仮説はあるか？"),
            ("falsify", "{topic}で現在の説明と競合仮説を区別する判定条件は何か？"),
            ("scale", "{topic}を一段小さいスケールで見ると何が変わるか？"),
            ("scale", "{topic}を一段大きいスケールで見ると何が変わるか？"),
        )
        pass_no = 0
        while len(questions) < target:
            kind, template = cycles[pass_no % len(cycles)]
            questions.append(InquiryQuestion(
                qid=f"g2-{serial:03d}",
                kind=kind,
                question=template.format(topic=topic),
                generation=2 + pass_no // len(cycles),
            ))
            serial += 1
            added += 1
            pass_no += 1
        return added

    def _inject_frontier(self, topic: str, questions: list[InquiryQuestion], target: int) -> int:
        if len(questions) >= target:
            return 0
        existing = {re.sub(r"\W+", "", q.question) for q in questions}
        added = 0
        serial = len(questions)
        for row in self.ledger.frontier_for(topic, min(128, target)):
            text = str(row.get("question", "")).strip()
            key = re.sub(r"\W+", "", text)
            if not text or key in existing:
                continue
            existing.add(key)
            questions.append(InquiryQuestion(
                qid=f"gf-{serial:03d}",
                kind=str(row.get("kind", "uncertainty")),
                question=text,
                generation=max(1, int(row.get("generation", 1) or 1)),
                parent_id="persistent-frontier",
                value_score=float(row.get("value_score", 0.0) or 0.0),
            ))
            serial += 1
            added += 1
            if len(questions) >= target:
                break
        return added

    def _score_questions(self, questions: list[InquiryQuestion], hits: list[RetrievalHit]) -> list[InquiryQuestion]:
        evidence_hint = max((float(h.score) for h in hits[:4]), default=0.0)
        ranked = self.scorer.rank(questions, evidence_hint)
        # Persistent frontier scores are lower bounds: do not erase prior value.
        for q in ranked:
            q.value_score = max(
                float(q.value_score),
                float(getattr(q, "value_score", 0.0) or 0.0),
            )
        return ranked

    def _learn(self, topic: str, questions: list[InquiryQuestion], confidence: float) -> dict:
        counts = {"promoted": 0, "reinforced": 0, "conflicts": 0, "skipped": 0, "recalled": 0}
        for q in questions:
            if q.recalled:
                counts["recalled"] += 1
                continue
            if not q.resolved:
                continue
            result = self.ledger.promote(
                topic=topic,
                kind=q.kind,
                question=q.question,
                answer=q.answer,
                evidence_ids=q.evidence_ids,
                value_score=q.value_score,
                confidence=confidence,
            )
            status = str(result.get("status", "skipped"))
            if status == "conflict":
                counts["conflicts"] += 1
            elif status in counts:
                counts[status] += 1
            else:
                counts["skipped"] += 1
        self.ledger.update_frontier(topic, questions)
        counts["ledger"] = self.ledger.stats()
        return counts

    @staticmethod
    def _best_overview(text: str, hits: list[RetrievalHit]) -> str:
        ranked: list[tuple[float, str]] = []
        seen: set[str] = set()
        for hit in hits[:6]:
            for sentence in sentences(hit.chunk.text):
                key = re.sub(r"\W+", "", sentence)[:220]
                if not key or key in seen:
                    continue
                seen.add(key)
                overlap = len(terms(sentence) & terms(text))
                score = hit.score + min(0.9, overlap * 0.12)
                if CUES["mechanism"].search(sentence):
                    score += 0.12
                ranked.append((score, sentence))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return "".join(_clean_sentence(s) for _, s in ranked[:4])

    def _audit_reply(self, topic: str, questions: list[InquiryQuestion]) -> str:
        resolved = sum(1 for q in questions if q.resolved)
        unresolved = len(questions) - resolved
        lines = [
            f"{topic}について、自己質問を大量生成して根拠で潰します。",
            f"生成 {len(questions)}問 / 解消 {resolved}問 / 未解決 {unresolved}問",
        ]

        # Keep the browser usable while the API still exposes every question.
        show = questions[:self.display_limit]
        for i, q in enumerate(show, 1):
            mark = "✓" if q.resolved else "?"
            if q.resolved:
                lines.append(f"{i:02d}. [{mark}] Q: {q.question}\n    A: {q.answer}")
            else:
                lines.append(f"{i:02d}. [{mark}] Q: {q.question}\n    A: 未解決。根拠不足として保持。")
        if len(questions) > len(show):
            lines.append(f"... 残り {len(questions) - len(show)}問は内部で保持・査定済みです。")
        return "\n".join(lines)

    def run(self, text: str, history: list[Mapping]) -> dict | None:
        t = str(text or "").strip()
        if len(t) < 2:
            return None

        context = self.index.context_from_history(history)
        hits = self.index.search(t, context, 12)
        if not hits or hits[0].score < 0.08:
            return None
        if not QUESTION_CUES.search(t) and len(t) < 12:
            return None

        target = self._target_from_text(t)
        topic = self._topic_label(hits, t)
        questions = self._generate_questions(topic, target)

        # Carry high-value unresolved questions across sessions, then expand the
        # generic question grid. Persistent questions are data, not router code.
        self._inject_frontier(topic, questions, target)
        self._fill_generic(topic, questions, target)
        questions = self._score_questions(questions, hits)

        # Pass 1 is value-prioritized. Large 2048-question bursts no longer spend
        # equal effort on near-duplicates before falsification/uncertainty tests.
        first_budget = min(len(questions), self.resolve_budget)
        for q in questions[:first_budget]:
            self._answer_question(q, t, hits)

        # Answer -> new question expansion can replace low-value filler slots
        # only while capacity remains.
        self._expand_from_answers(topic, t, context, questions, target)
        questions = self._score_questions(questions, hits)

        rounds = 1
        for round_no in range(2, self.max_rounds + 1):
            progress = self._resolve_round(t, context, questions, hits)
            rounds = round_no
            added = self._expand_from_answers(topic, t, context, questions, target)
            if added:
                questions = self._score_questions(questions, hits)
            if progress == 0 and added == 0:
                break

        audit_mode = bool(AUDIT_CUES.search(t))
        current_request = bool(CURRENT_CUES.search(t))
        resolved = sum(1 for q in questions if q.resolved)
        unresolved = len(questions) - resolved

        evidence = [{
            "id": hit.chunk.chunk_id,
            "title": hit.chunk.title,
            "source": hit.chunk.source,
            "score": hit.score,
        } for hit in hits[:8]]

        needs_live_data = bool(current_request and any(
            CUES["live_data"].search(h.chunk.text) for h in hits[:8]
        ))

        base_confidence = round(min(0.97, 0.68 + hits[0].score * 0.24), 3)
        learning = self._learn(topic, questions, base_confidence)

        if audit_mode:
            reply = self._audit_reply(topic, questions)
        else:
            reply = self._best_overview(t, hits)
            if not reply:
                return None
            reply += f" 内部では{len(questions)}問を生成し、{resolved}問を根拠付きで解消、{unresolved}問を未解決として保持しました。"
            if needs_live_data:
                reply += " 現在値・最新予測の確定には静的知識ではなく最新データが必要です。"

        return {
            "ok": True,
            "reply": reply,
            "confidence": base_confidence,
            "needs_teacher": False,
            "local": True,
            "inquiry_reasoning": True,
            "question_generation": True,
            "question_resolution": True,
            "answer_to_question_expansion": True,
            "question_value_ranking": True,
            "persistent_epistemic_learning": True,
            "contradiction_quarantine": True,
            "topic_specific_routing": False,
            "topic": topic,
            "target_questions": target,
            "inquiry_rounds": rounds,
            "generated_questions": len(questions),
            "resolved_questions": resolved,
            "unresolved_questions": unresolved,
            "resolution_rate": round(resolved / max(1, len(questions)), 3),
            "audit_mode": audit_mode,
            "needs_live_data": needs_live_data,
            "questions": [{
                "id": q.qid,
                "kind": q.kind,
                "question": q.question,
                "generation": q.generation,
                "parent_id": q.parent_id,
                "value_score": q.value_score,
                "attempts": q.attempts,
                "recalled": q.recalled,
                "resolved": q.resolved,
                "answer": q.answer,
                "evidence_ids": list(q.evidence_ids),
            } for q in questions],
            "evidence": evidence,
            "epistemic_learning": learning,
        }
