from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SENT = re.compile(r"(?<=[.!?。！？])\s+|[\r\n]+")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.I)

APPRAISAL_SPECS: tuple[tuple[str, str, re.Pattern], ...] = (
    ("question", "研究質問・目的は明示されているか？", re.compile(r"\b(objective|aim|purpose|we (?:test|investigate|examine|assess|evaluate|study))\b|目的|検討|評価", re.I)),
    ("design", "研究デザインは特定できるか？", re.compile(r"\b(randomi[sz]ed|cohort|case.control|cross.sectional|meta.analysis|systematic review|simulation|experiment|observational|prospective|retrospective)\b|無作為|コホート|症例対照|横断|メタ解析|シミュレーション|実験", re.I)),
    ("sample", "対象・サンプルは記述されているか？", re.compile(r"\b(n\s*=\s*\d+|participants?|patients?|subjects?|samples?|dataset|observations?)\b|参加者|患者|対象|サンプル|データセット|観測", re.I)),
    ("exposure", "介入・曝露・入力条件は明示されているか？", re.compile(r"\b(intervention|exposure|treatment|input|forcing|initial condition|perturbation)\b|介入|曝露|入力|外力|初期条件|摂動", re.I)),
    ("outcome", "主要アウトカム・評価量は明示されているか？", re.compile(r"\b(outcome|endpoint|accuracy|error|skill|effect|response|performance)\b|アウトカム|評価|精度|誤差|効果|応答|性能", re.I)),
    ("method", "解析・測定方法は説明されているか？", re.compile(r"\b(method|model|measurement|assay|algorithm|analysis|instrument|satellite|radar)\b|方法|モデル|測定|解析|アルゴリズム|衛星|レーダー", re.I)),
    ("control", "比較群・対照・ベースラインはあるか？", re.compile(r"\b(control|placebo|baseline|reference|comparison|compared with|versus|vs\.)\b|対照|比較|ベースライン|基準", re.I)),
    ("uncertainty", "不確実性・信頼区間・誤差は示されているか？", re.compile(r"\b(confidence interval|credible interval|uncertaint|standard error|error bar|variance|bootstrap)\b|信頼区間|不確実|標準誤差|分散|誤差", re.I)),
    ("effect_size", "効果量・定量的な差は示されているか？", re.compile(r"\b(effect size|odds ratio|hazard ratio|risk ratio|relative risk|mean difference|correlation|r\s*=|%\b)\b|効果量|オッズ比|ハザード比|相対リスク|相関", re.I)),
    ("statistics", "統計的検定・推定手法は明示されているか？", re.compile(r"\b(p\s*[<=>]\s*0?\.\d+|bayesian|regression|anova|mixed model|likelihood|posterior|frequentist)\b|回帰|分散分析|ベイズ|尤度|事後分布", re.I)),
    ("assumptions", "主要な仮定・近似は記述されているか？", re.compile(r"\b(assum|approximation|idealized|parameteri[sz]ation|simplif)\b|仮定|近似|理想化|パラメタリゼーション", re.I)),
    ("confounding", "交絡・代替説明は検討されているか？", re.compile(r"\b(confound|alternative explanation|covariate|adjusted for|sensitivity analysis)\b|交絡|代替説明|共変量|感度分析", re.I)),
    ("bias", "バイアスの可能性は検討されているか？", re.compile(r"\b(bias|selection bias|measurement bias|publication bias)\b|バイアス|選択偏り|出版バイアス", re.I)),
    ("missing_data", "欠測・除外・データ品質は扱われているか？", re.compile(r"\b(missing data|excluded|quality control|imputation|data quality)\b|欠測|除外|品質管理|補完", re.I)),
    ("robustness", "頑健性・感度分析はあるか？", re.compile(r"\b(robust|sensitivity analysis|ablation|stress test|perturbation test)\b|頑健|感度分析|アブレーション|ストレステスト", re.I)),
    ("validation", "独立検証・外部検証はあるか？", re.compile(r"\b(external validation|independent validation|held.out|test set|out.of.sample)\b|外部検証|独立検証|テストセット|標本外", re.I)),
    ("replication", "再現・追試可能性は示されているか？", re.compile(r"\b(reproduc|replicat|code available|data available|open source)\b|再現|追試|コード公開|データ公開", re.I)),
    ("mechanism", "観測された結果の機構説明はあるか？", re.compile(r"\b(mechanism|causal pathway|mediator|process|dynamics)\b|機構|因果経路|媒介|過程|ダイナミクス", re.I)),
    ("causality", "因果主張と研究デザインは整合しているか？", re.compile(r"\b(causal|causality|cause|causes|caused by)\b|因果|原因", re.I)),
    ("generalization", "一般化可能性・適用範囲は議論されているか？", re.compile(r"\b(generali[sz]|external validity|applicab|transferab)\b|一般化|外的妥当性|適用範囲", re.I)),
    ("limitations", "限界は明示されているか？", re.compile(r"\b(limitations?|caveat|cannot|may not|uncertain)\b|限界|注意点|できない|不確実", re.I)),
    ("contradiction", "既存研究との不一致・競合仮説は扱われているか？", re.compile(r"\b(in contrast|contradict|inconsistent|conflict|disagree|alternative hypothesis)\b|矛盾|不一致|競合仮説|対照的", re.I)),
    ("extremes", "極端条件・境界条件でも成立するか？", re.compile(r"\b(extreme|boundary condition|edge case|rare event|tail)\b|極端|境界条件|稀な事象|裾", re.I)),
    ("scale", "時間・空間・組織スケール依存性は検討されているか？", re.compile(r"\b(scale|spatial|temporal|resolution|multiscale)\b|スケール|空間|時間|解像度|多尺度", re.I)),
    ("prospective_prediction", "事後説明ではなく前向き予測を検証しているか？", re.compile(r"\b(prospective|forecast|predictive validation|pre.register|preregister)\b|前向き|予測検証|事前登録", re.I)),
    ("data_provenance", "データ源と来歴は明示されているか？", re.compile(r"\b(data source|database|registry|repository|dataset)\b|データ源|データベース|レジストリ|リポジトリ", re.I)),
    ("ethics", "倫理・利益相反・資金源の情報があるか？", re.compile(r"\b(ethics|institutional review board|IRB|conflict of interest|funding|funded by)\b|倫理|利益相反|資金|研究費", re.I)),
    ("correction_status", "訂正・撤回・更新情報を確認したか？", re.compile(r"\b(retract|correction|erratum|expression of concern|updated)\b|撤回|訂正|懸念表明|更新", re.I)),
    ("novelty", "新規性が具体的に示されているか？", re.compile(r"\b(novel|first|new approach|for the first time)\b|新規|初めて|新しい手法", re.I)),
    ("practical_significance", "統計的有意性と実質的重要性を区別できるか？", re.compile(r"\b(clinically significant|practical significance|meaningful|magnitude)\b|臨床的意義|実質的|重要性|大きさ", re.I)),
    ("future_test", "次に何を検証すべきか示されているか？", re.compile(r"\b(future work|future research|further study|should be tested)\b|今後|将来研究|追加検証", re.I)),
    ("open_question", "結論から新しい未解決問題を生成できるか？", re.compile(r"\b(unknown|remains unclear|open question|not understood)\b|不明|未解明|明らかでない", re.I)),
)


def _clean(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = _TAG.sub(" ", value)
    return _WS.sub(" ", value).strip()


def _first(seq, default=""):
    if isinstance(seq, list) and seq:
        return seq[0]
    return default


def _date_parts(value) -> str:
    try:
        parts = value["date-parts"][0]
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        d = int(parts[2]) if len(parts) > 2 else 1
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return ""


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in _SENT.split(_clean(text)) if len(x.strip()) >= 12]


@dataclass
class ReviewQuestion:
    kind: str
    question: str
    resolved: bool
    evidence: str = ""


@dataclass
class PaperReview:
    doi: str
    title: str
    journal: str
    published: str
    indexed: str
    url: str
    type: str
    publisher: str
    subjects: list[str]
    author_count: int
    reference_count: int
    cited_by_count: int
    abstract_available: bool
    screening_status: str
    update_flags: list[str]
    generated_questions: int
    resolved_questions: int
    unresolved_questions: int
    resolution_rate: float
    review_questions: list[dict]
    abstract: str = ""


class CriticalAppraiser:
    """High-volume abstract/metadata critical appraisal.

    This is *not* formal journal peer review. It screens what can be checked
    from bibliographic metadata and the abstract and keeps everything else
    unresolved instead of inventing an answer.
    """

    @staticmethod
    def _evidence(text: str, pattern: re.Pattern) -> str:
        for sentence in _sentences(text):
            if pattern.search(sentence):
                # Keep only a short local evidence fragment in the runtime cache.
                return sentence[:360]
        return ""

    @staticmethod
    def _update_flags(item: dict) -> list[str]:
        flags = []
        if item.get("update-to"):
            flags.append("update-to")
        if item.get("updated-by"):
            flags.append("updated-by")
        relation = item.get("relation")
        if relation:
            flags.append("relation")
        subtype = str(item.get("subtype", "")).lower()
        if any(x in subtype for x in ("retract", "correct", "erratum")):
            flags.append(subtype)
        return flags

    def review(self, item: dict, store_abstract: bool = False) -> PaperReview:
        title = _clean(_first(item.get("title"), ""))
        abstract = _clean(item.get("abstract", ""))
        journal = _clean(_first(item.get("container-title"), ""))
        doi = str(item.get("DOI", "")).strip().lower()
        url = str(item.get("URL", "")).strip()
        published = _date_parts(item.get("published") or item.get("published-online") or item.get("issued"))
        indexed = ""
        try:
            indexed = str(item.get("indexed", {}).get("date-time", ""))[:10]
        except Exception:
            pass

        text = " ".join((title, abstract))
        questions: list[ReviewQuestion] = []
        for kind, question, pattern in APPRAISAL_SPECS:
            evidence = self._evidence(text, pattern)
            questions.append(ReviewQuestion(kind, question, bool(evidence), evidence))

        # Metadata can directly resolve a few appraisal questions.
        refs = item.get("reference") or []
        authors = item.get("author") or []
        if refs:
            questions.append(ReviewQuestion("references", "参考文献情報は登録されているか？", True, f"Crossref references={len(refs)}"))
        else:
            questions.append(ReviewQuestion("references", "参考文献情報は登録されているか？", False, ""))
        if doi and _DOI.match(doi):
            questions.append(ReviewQuestion("persistent_id", "永続識別子DOIがあるか？", True, doi))
        else:
            questions.append(ReviewQuestion("persistent_id", "永続識別子DOIがあるか？", False, ""))

        resolved = sum(1 for q in questions if q.resolved)
        flags = self._update_flags(item)
        screening = "journal-article-metadata"
        if abstract:
            screening += "+abstract"
        if flags:
            screening += "+post-publication-update-flag"

        return PaperReview(
            doi=doi,
            title=title,
            journal=journal,
            published=published,
            indexed=indexed,
            url=url,
            type=str(item.get("type", "")),
            publisher=_clean(item.get("publisher", "")),
            subjects=[_clean(x) for x in (item.get("subject") or [])[:12]],
            author_count=len(authors),
            reference_count=len(refs),
            cited_by_count=int(item.get("is-referenced-by-count", 0) or 0),
            abstract_available=bool(abstract),
            screening_status=screening,
            update_flags=flags,
            generated_questions=len(questions),
            resolved_questions=resolved,
            unresolved_questions=len(questions) - resolved,
            resolution_rate=round(resolved / max(1, len(questions)), 4),
            review_questions=[asdict(q) for q in questions],
            abstract=abstract if store_abstract else "",
        )


class CrossrefHarvester:
    BASE = "https://api.crossref.org/works"

    def __init__(self, mailto: str = "", rows: int = 1000, timeout: int = 30):
        self.mailto = mailto.strip()
        self.rows = max(20, min(1000, int(rows)))
        self.timeout = max(5, int(timeout))

    def _request(self, params: dict) -> dict:
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            self.BASE + "?" + query,
            headers={
                "User-Agent": f"FAP-LiteratureReview/1.0 ({self.mailto or 'no-contact'})",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def iter_works(
        self,
        from_date: str,
        until_date: str,
        max_works: int = 0,
        query: str = "",
    ) -> Iterable[dict]:
        cursor = "*"
        seen = 0
        while True:
            filters = [
                f"from-index-date:{from_date}",
                f"until-index-date:{until_date}",
                "type:journal-article",
            ]
            params = {
                "filter": ",".join(filters),
                "rows": self.rows,
                "cursor": cursor,
                "cursor-max": self.rows,
            }
            if self.mailto:
                params["mailto"] = self.mailto
            if query.strip():
                params["query.bibliographic"] = query.strip()

            data = self._request(params)
            message = data.get("message", {})
            items = message.get("items") or []
            if not items:
                break
            for item in items:
                yield item
                seen += 1
                if max_works and seen >= max_works:
                    return
            nxt = str(message.get("next-cursor", ""))
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            time.sleep(0.05)


def run_review(
    *,
    from_date: str,
    until_date: str,
    output: Path,
    summary_path: Path,
    max_works: int,
    query: str,
    store_abstract: bool,
    mailto: str,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    appraiser = CriticalAppraiser()
    harvester = CrossrefHarvester(mailto=mailto)
    totals = Counter()
    journals = Counter()
    unresolved_kinds = Counter()
    resolved_kinds = Counter()

    with output.open("w", encoding="utf-8") as fh:
        for item in harvester.iter_works(from_date, until_date, max_works=max_works, query=query):
            review = appraiser.review(item, store_abstract=store_abstract)
            totals["works"] += 1
            totals["questions"] += review.generated_questions
            totals["resolved"] += review.resolved_questions
            totals["unresolved"] += review.unresolved_questions
            totals["abstracts"] += int(review.abstract_available)
            totals["update_flags"] += int(bool(review.update_flags))
            if review.journal:
                journals[review.journal] += 1
            for q in review.review_questions:
                if q["resolved"]:
                    resolved_kinds[q["kind"]] += 1
                else:
                    unresolved_kinds[q["kind"]] += 1
            fh.write(json.dumps(asdict(review), ensure_ascii=False) + "\n")

    summary = {
        "provider": "Crossref REST API",
        "from_index_date": from_date,
        "until_index_date": until_date,
        "query": query,
        "max_works": max_works,
        "screening_scope": "journal-article metadata; abstract critical appraisal where abstract metadata is present",
        "formal_peer_review": False,
        "formal_peer_review_note": "Automated screening is not a substitute for independent expert peer review or full-text methodological review.",
        "works_processed": totals["works"],
        "abstracts_available": totals["abstracts"],
        "questions_generated": totals["questions"],
        "questions_resolved_from_metadata_or_abstract": totals["resolved"],
        "questions_unresolved": totals["unresolved"],
        "resolution_rate": round(totals["resolved"] / max(1, totals["questions"]), 4),
        "records_with_post_publication_update_flags": totals["update_flags"],
        "top_journals": journals.most_common(30),
        "most_unresolved_question_types": unresolved_kinds.most_common(20),
        "most_resolved_question_types": resolved_kinds.most_common(20),
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Broad recent-literature screening and question-resolution pipeline.")
    ap.add_argument("--from-date", default="")
    ap.add_argument("--until-date", default="")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--max-works", type=int, default=10000, help="0 = no explicit cap")
    ap.add_argument("--query", default="")
    ap.add_argument("--output", default="runtime/literature/latest_reviews.jsonl")
    ap.add_argument("--summary", default="runtime/literature/latest_summary.json")
    ap.add_argument("--store-abstract", action="store_true")
    ap.add_argument("--mailto", default=os.environ.get("CROSSREF_MAILTO", ""))
    args = ap.parse_args()

    today = dt.date.today()
    until = args.until_date or today.isoformat()
    start = args.from_date or (today - dt.timedelta(days=max(1, args.days))).isoformat()

    try:
        summary = run_review(
            from_date=start,
            until_date=until,
            output=Path(args.output),
            summary_path=Path(args.summary),
            max_works=max(0, args.max_works),
            query=args.query,
            store_abstract=args.store_abstract,
            mailto=args.mailto,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
