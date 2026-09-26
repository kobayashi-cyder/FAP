from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Optional


OPERATORS = ("reframe", "analogy", "inversion", "combination", "constraint_shift")

BOOTSTRAP_CHALLENGES = (
    ("reframe", "低RAMで会話能力を高める", "RAM 制約 会話"),
    ("analogy", "異分野の仕組みから新しい学習方法を考える", "学習 類推 構造"),
    ("inversion", "通常の前提を外して省メモリ推論を考える", "前提 省メモリ 推論"),
    ("combination", "記憶と仮説探索を組み合わせた機能を考える", "記憶 仮説 探索"),
    ("constraint_shift", "厳しい容量制約の中で創造性を高める", "容量 制約 創造性"),
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_+\-]+|[一-龥ぁ-んァ-ンー]{2,}", (text or "").lower())


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(1, len(sa | sb))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class CreativeCandidate:
    text: str
    operator: str
    novelty: float
    utility: float
    consistency: float
    diversity: float
    score: float


@dataclass(frozen=True)
class CreativeExperience:
    task_id: str
    task_text: str
    operator: str
    candidate_digest: str
    evidence_id: str
    reward: float
    verified: bool
    stage: str


class CreativeExperienceStore:
    """Verified creativity ledger with replay protection and persisted success priors."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self.records: list[dict] = []
        self.seen_evidence: set[str] = set()
        if self.path and self.path.is_file():
            self._merge_payload(self.path)

    def _merge_payload(self, path: Path) -> None:
        from .experience_validation import validate_experience_payload

        payload = json.loads(path.read_text(encoding="utf-8"))
        records = validate_experience_payload(payload)
        for raw in records:
            record = dict(raw)
            evidence_id = str(record.get("evidence_id", "")).strip()
            if not evidence_id:
                raise ValueError("creativity experience missing evidence_id")
            if evidence_id in self.seen_evidence:
                continue
            if record.get("operator") not in OPERATORS:
                raise ValueError("unknown creativity operator in experience store")
            self.records.append(record)
            self.seen_evidence.add(evidence_id)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"records": self.records}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def observe(
        self,
        *,
        task_id: str,
        task_text: str,
        candidate: CreativeCandidate,
        evidence_id: str,
        reward: float,
        verified: bool,
    ) -> CreativeExperience:
        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise ValueError("evidence_id is required")
        if evidence_id in self.seen_evidence:
            raise ValueError("duplicate creativity evidence")
        digest = sha256(
            (candidate.operator + "\n" + candidate.text).encode("utf-8")
        ).hexdigest()
        successful = bool(verified) and float(reward) >= 0.70 and candidate.score >= 0.65
        prior = [
            r for r in self.records
            if r.get("operator") == candidate.operator
            and r.get("verified") is True
            and float(r.get("reward", 0.0)) >= 0.70
            and r.get("stage") in {"ephemeral", "shadow", "consolidated"}
        ]
        success_count = len(prior) + (1 if successful else 0)
        if not successful:
            stage = "rejected"
        elif success_count >= 3:
            stage = "consolidated"
        elif success_count >= 2:
            stage = "shadow"
        else:
            stage = "ephemeral"
        record = CreativeExperience(
            task_id=str(task_id),
            task_text=str(task_text),
            operator=candidate.operator,
            candidate_digest=digest,
            evidence_id=evidence_id,
            reward=_clamp(reward),
            verified=bool(verified),
            stage=stage,
        )
        self.records.append(asdict(record))
        self.seen_evidence.add(evidence_id)
        self._save()
        return record

    def operator_weights(self, task_text: str = "") -> dict[str, float]:
        weights = {name: 1.0 for name in OPERATORS}
        query = _tokens(task_text)
        for record in self.records:
            if record.get("verified") is not True:
                continue
            reward = _clamp(record.get("reward", 0.0))
            stage = record.get("stage")
            gain = {"ephemeral": 0.05, "shadow": 0.12, "consolidated": 0.25}.get(stage, 0.0)
            if not gain:
                continue
            prior_task = _tokens(str(record.get("task_text", "")))
            similarity = _jaccard(query, prior_task) if query and prior_task else 0.0
            relevance = 0.10 + 0.90 * similarity
            op = str(record.get("operator"))
            if op in weights:
                weights[op] += gain * reward * relevance
        return weights

    def consolidated_operators(self) -> list[str]:
        return sorted({
            str(r["operator"])
            for r in self.records
            if r.get("verified") is True and r.get("stage") == "consolidated"
        })


class CreativityEngine:
    """Divergent search that reuses only verified, deduplicated creative experience."""

    def __init__(
        self,
        experience_store: Optional[CreativeExperienceStore] = None,
        *,
        use_bundled_experience: bool = True,
    ):
        self.experience_store = experience_store or CreativeExperienceStore()
        if experience_store is None and use_bundled_experience:
            self._bootstrap_verified_successes()

    def _anchors(self, task: str, context: str) -> tuple[str, str, str]:
        toks = []
        seen = set()
        for token in _tokens(task + " " + context):
            if token not in seen:
                seen.add(token)
                toks.append(token)
        while len(toks) < 3:
            toks.append(("目的", "制約", "利用者")[len(toks)])
        return toks[0], toks[1], toks[2]

    def _render(self, operator: str, task: str, context: str) -> str:
        a, b, c = self._anchors(task, context)
        if operator == "reframe":
            return f"「{task}」を『{a}を達成する問題』ではなく『{b}を再設計する問題』として捉え直す。"
        if operator == "analogy":
            return f"「{task}」を別領域の『{a}→{b}→{c}』という流れになぞらえ、対応関係から新案を作る。"
        if operator == "inversion":
            return f"「{task}」で通常守る前提を一つ反転し、『{b}をしないならどう実現するか』から案を出す。"
        if operator == "combination":
            return f"「{task}」について『{a}』と『{c}』を一つの仕組みに結合し、単独では出ない機能を作る。"
        if operator == "constraint_shift":
            return f"「{task}」の制約『{b}』を固定条件ではなく探索変数として扱い、極端な最小・最大条件でも成立する案を探す。"
        raise ValueError("unknown creativity operator")

    def verify_candidate(self, task: str, candidate: CreativeCandidate) -> tuple[bool, float]:
        """Objective mechanism gate; it does not claim human-level creative quality."""
        checks = (
            candidate.operator in OPERATORS,
            bool(candidate.text.strip()),
            str(task) in candidate.text,
            candidate.novelty >= 0.35,
            candidate.utility >= 0.55,
            candidate.consistency >= 0.75,
            candidate.diversity >= 0.45,
            candidate.score >= 0.65,
        )
        passed = sum(bool(x) for x in checks)
        reward = passed / len(checks)
        return passed == len(checks), round(reward, 4)

    def _bootstrap_verified_successes(self) -> None:
        for operator, task, context in BOOTSTRAP_CHALLENGES:
            candidates = self.generate(task, context, count=5)
            candidate = next((x for x in candidates if x.operator == operator), None)
            if candidate is None:
                continue
            verified, reward = self.verify_candidate(task, candidate)
            if not verified:
                continue
            for attempt in range(3):
                self.experience_store.observe(
                    task_id=f"bootstrap:{operator}:{attempt}",
                    task_text=(task + " " + context).strip(),
                    candidate=candidate,
                    evidence_id=f"v79-bootstrap:{operator}:{attempt}",
                    reward=reward,
                    verified=True,
                )

    def generate(self, task: str, context: str = "", *, count: int = 5) -> list[CreativeCandidate]:
        task = str(task or "").strip()
        if not task:
            return []
        full_task = (task + " " + context).strip()
        weights = self.experience_store.operator_weights(full_task)
        task_tokens = _tokens(full_task)
        raw: list[CreativeCandidate] = []
        prior_texts: list[str] = []
        for operator in OPERATORS:
            text = self._render(operator, task, context)
            cand_tokens = _tokens(text)
            overlap = _jaccard(task_tokens, cand_tokens)
            novelty = _clamp(1.0 - overlap)
            utility = _clamp(0.55 + 0.35 * min(1.0, overlap * 2.0))
            consistency = 1.0 if task in text else 0.75
            diversity = 1.0
            if prior_texts:
                diversity = _clamp(1.0 - max(_jaccard(cand_tokens, _tokens(x)) for x in prior_texts))
            learned = min(1.35, weights.get(operator, 1.0))
            base = 0.30 * novelty + 0.30 * utility + 0.25 * consistency + 0.15 * diversity
            score = _clamp(base * learned)
            raw.append(CreativeCandidate(
                text=text,
                operator=operator,
                novelty=round(novelty, 4),
                utility=round(utility, 4),
                consistency=round(consistency, 4),
                diversity=round(diversity, 4),
                score=round(score, 4),
            ))
            prior_texts.append(text)
        raw.sort(key=lambda x: (-x.score, x.operator))
        return raw[: max(1, min(int(count), len(raw)))]

    def recombine(self, candidates: list[CreativeCandidate], *, top_k: int = 2) -> str:
        if not candidates:
            return ""
        chosen = candidates[: max(1, min(top_k, len(candidates)))]
        methods = " + ".join(c.operator for c in chosen)
        ideas = " / ".join(c.text for c in chosen)
        return f"再結合[{methods}]: {ideas}"

    def verified_success(
        self,
        *,
        task_id: str,
        task_text: str,
        candidate: CreativeCandidate,
        evidence_id: str,
        reward: float,
    ) -> CreativeExperience:
        verified, mechanism_reward = self.verify_candidate(task_text.split(" ")[0], candidate)
        final_reward = min(_clamp(reward), mechanism_reward)
        return self.experience_store.observe(
            task_id=task_id,
            task_text=task_text,
            candidate=candidate,
            evidence_id=evidence_id,
            reward=final_reward,
            verified=verified,
        )


class CreativityAugmentedResponder:
    """Adds divergent proposals to a base responder without promoting them to facts."""

    def __init__(
        self,
        base_responder: Callable[[str, str, str], str],
        *,
        engine: Optional[CreativityEngine] = None,
        max_candidates: int = 3,
    ):
        if not callable(base_responder):
            raise TypeError("base_responder must be callable")
        self.base_responder = base_responder
        self.engine = engine or CreativityEngine()
        self.max_candidates = max(1, int(max_candidates))

    def __call__(self, user_text: str, context: str, mode: str) -> str:
        candidates = self.engine.generate(user_text, context, count=self.max_candidates)
        augmented = context.rstrip()
        if candidates:
            lines = [
                augmented,
                "[FAP creativity guidance]",
                "These are hypotheses/ideas, not facts.",
            ]
            for c in candidates:
                lines.append(f"{c.operator}: {c.text}")
            lines.append(self.engine.recombine(candidates))
            augmented = "\n".join(x for x in lines if x)
        output = str(self.base_responder(user_text, augmented, mode)).strip()
        if not output:
            raise ValueError("base responder returned empty text")
        return output
