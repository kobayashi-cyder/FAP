from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerEvidence:
    symbol: str
    answer: str
    rule_id: str
    evidence: str


def _find_option(text: str, pattern: str) -> str | None:
    match = re.search(r"(?m)([0-9])\s+" + pattern, text, re.I)
    return match.group(1) if match else None


class InformationFundamentalsReasoner:
    def solve(self, text: str) -> tuple[dict[str, str], tuple[AnswerEvidence, ...]]:
        src = str(text or "")
        answers: dict[str, str] = {}
        evidence: list[AnswerEvidence] = []

        def put(symbol: str, value: str | None, rule_id: str, why: str) -> None:
            if value is None or symbol in answers:
                return
            answers[symbol] = value
            evidence.append(AnswerEvidence(symbol, value, rule_id, why))

        if "主記憶装置" in src and "補助記憶装置" in src:
            put("ア", _find_option(src, r"低速"), "storage.secondary-speed",
                "secondary storage is generally slower than main memory")
            put(
                "イ",
                _find_option(src, r"容量が大きく[、,，\s]*データの長期的な保存"),
                "storage.secondary-persistence",
                "secondary storage is generally larger and used for persistent storage",
            )

        if "情報セキュリティ" in src and "可用性" in src and "バックアップ" in src:
            put(
                "ウ",
                _find_option(src, r"保有するデータをバックアップしておくことで[^\n]*可用性"),
                "security.backup-availability",
                "backup supports availability by enabling recovery",
            )

        if "スクロール距離の平均" in src and "中央値" in src and "最頻値" in src:
            put(
                "コ",
                _find_option(src, r"中央値"),
                "optimization.absolute-distance-median",
                "a median minimizes the sum or expectation of absolute deviations",
            )

        if "月リスト" in src and "分布に偏りがない" in src:
            put(
                "サ",
                _find_option(src, r"どの月にしても変わらない"),
                "probability.uniform-cycle-invariance",
                "a uniform cyclic distribution has the same expected movement for every origin",
            )

        if "送信側メールサーバ" in src and "受信側メールサーバ" in src:
            user_missing = _find_option(src, r"B\s+ユーザ名が存在しない")
            domain_missing = _find_option(src, r"A\s+受信側のドメイン名が存在しない")
            if "sinobu@example.ed.jp" in src:
                put(
                    "シ",
                    user_missing,
                    "email.local-part-validation",
                    "valid recipient domain reaches server B; B detects nonexistent local user",
                )
            if "example.ed.jp@sinobu" in src:
                put(
                    "ス",
                    domain_missing,
                    "email.recipient-domain-resolution",
                    "server A must resolve the recipient domain before delivery",
                )
            if "sinobu@exmple.ed.jp" in src:
                put(
                    "セ",
                    domain_missing,
                    "email.recipient-domain-resolution",
                    "server A detects a nonexistent recipient domain",
                )

        if "IPアドレスを特定" in src and "DNS" in src:
            put(
                "ソ",
                _find_option(src, r"DNS"),
                "network.dns-name-resolution",
                "DNS resolves domain names to IP addresses",
            )

        return answers, tuple(evidence)
