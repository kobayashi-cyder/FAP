from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


_JAPANESE = re.compile(r"[ぁ-んァ-ン一-龥]")


@dataclass(frozen=True)
class FactualAnswer:
    fact_id: str
    patterns: tuple[Pattern[str], ...]
    ja: str
    en: str
    category: str = "general"
    confidence: float = 0.995


def _rx(*patterns: str) -> tuple[Pattern[str], ...]:
    return tuple(re.compile(p, re.I) for p in patterns)


FACTS: tuple[FactualAnswer, ...] = (
    FactualAnswer(
        "vacuum_speed_of_light",
        _rx(
            r"(?:真空(?:中|内)?の?)?(?:光速|光速度).*(?:何|いくつ|いくら|値|速度|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:真空(?:中|内)?の?)?(?:光速|光速度)",
            r"(?:speed\s+of\s+light|light\s+speed).*(?:vacuum|in\s+vacuo|what|value|\?)",
            r"(?:vacuum|in\s+vacuo).*(?:speed\s+of\s+light|light\s+speed)",
        ),
        "真空中の光速度 c は 299,792,458 m/s です。約 3.00×10^8 m/s（約30万 km/s）で、SIではこの値は正確に定義されています。",
        "The speed of light in vacuum, c, is exactly 299,792,458 m/s (about 3.00×10^8 m/s).",
        "physics",
    ),
    FactualAnswer(
        "planck_constant",
        _rx(
            r"(?:プランク定数|planck(?:'s)?\s+constant).*(?:何|いくつ|いくら|値|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:プランク定数|planck(?:'s)?\s+constant)",
        ),
        "プランク定数 h は 6.62607015×10^-34 J·s です。SIでは正確に定義されています。",
        "Planck's constant h is exactly 6.62607015×10^-34 J·s in SI.",
        "physics",
    ),
    FactualAnswer(
        "elementary_charge",
        _rx(
            r"(?:電気素量|素電荷|elementary\s+charge).*(?:何|いくつ|いくら|値|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:電気素量|素電荷|elementary\s+charge)",
        ),
        "電気素量 e は 1.602176634×10^-19 C です。SIでは正確に定義されています。",
        "The elementary charge e is exactly 1.602176634×10^-19 C in SI.",
        "physics",
    ),
    FactualAnswer(
        "boltzmann_constant",
        _rx(
            r"(?:ボルツマン定数|boltzmann\s+constant).*(?:何|いくつ|いくら|値|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:ボルツマン定数|boltzmann\s+constant)",
        ),
        "ボルツマン定数 k は 1.380649×10^-23 J/K です。SIでは正確に定義されています。",
        "The Boltzmann constant k is exactly 1.380649×10^-23 J/K in SI.",
        "physics",
    ),
    FactualAnswer(
        "avogadro_constant",
        _rx(
            r"(?:アボガドロ定数|avogadro(?:'s)?\s+constant).*(?:何|いくつ|いくら|値|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:アボガドロ定数|avogadro(?:'s)?\s+constant)",
        ),
        "アボガドロ定数 N_A は 6.02214076×10^23 mol^-1 です。SIでは正確に定義されています。",
        "The Avogadro constant N_A is exactly 6.02214076×10^23 mol^-1 in SI.",
        "physics",
    ),
    FactualAnswer(
        "standard_gravity",
        _rx(
            r"(?:標準重力加速度|standard\s+gravity).*(?:何|いくつ|いくら|値|\?|？|は$)",
            r"(?:何|いくつ|いくら).*(?:標準重力加速度|standard\s+gravity)",
        ),
        "標準重力加速度 g₀ は 9.80665 m/s² です。",
        "Standard gravity g₀ is 9.80665 m/s².",
        "physics",
    ),
)


class FactualQAOrgan:
    """Small, high-precision local fact path.

    It intentionally answers only facts with explicit deterministic entries.
    Unknown factual questions fall through to the existing reasoning/teacher
    paths instead of fabricating a value.
    """

    def match(self, text: str) -> FactualAnswer | None:
        t = str(text or "").strip()
        if not t:
            return None
        for fact in FACTS:
            if any(p.search(t) for p in fact.patterns):
                return fact
        return None

    def run(self, text: str) -> dict | None:
        fact = self.match(text)
        if fact is None:
            return None
        reply = fact.ja if _JAPANESE.search(str(text or "")) else fact.en
        return {
            "ok": True,
            "reply": reply,
            "confidence": fact.confidence,
            "needs_teacher": False,
            "local": True,
            "factual_qa": True,
            "answer_coverage": True,
            "fact_id": fact.fact_id,
            "fact_category": fact.category,
        }
